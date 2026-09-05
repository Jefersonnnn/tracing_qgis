# Análise de performance — tracing_qgis

Repositório clonado de `https://github.com/Jefersonnnn/tracing_qgis` (commit `745b4f6`).
Plugin QGIS que, a partir de uma rede selecionada, percorre o grafo de tubulações
(`TracingPipelines`) procurando os registros de manobra a fechar, com etapas auxiliares
em `FindPoints` e `LancamentoRamal`.

A seguir, os pontos que mais impactam desempenho, do mais crítico ao mais cosmético.

---

## 1. Índice espacial construído no `__init__` (thread da GUI) — CRÍTICO

`TracingPipelines.__create_spatial_index()`, `FindPoints` e `LancamentoRamal` criam o
`QgsSpatialIndex` sobre **todas** as feições no construtor, que roda na thread da interface
**antes** da `QgsTask` começar. Em camadas grandes isso congela o QGIS por vários segundos.

**Correção:** mover a construção do índice para dentro de `run()` (que já roda em background).

```python
def run(self):
    self.__create_spatial_index()   # agora em background
    ...
```

Além disso, passar `QgsFeatureRequest().setSubsetOfAttributes([])` / `setNoAttributes()`
ao `getFeatures()` usado só para indexar — não é preciso carregar atributos.

---

## 2. `threading.Thread` por pipeline — CRÍTICO (correção + risco de crash)

Em `TracingPipelines.run()`:

```python
thread1 = threading.Thread(target=self.__find_neighbors, args=(v1, pipeline_id))
thread2 = threading.Thread(target=self.__find_neighbors, args=(v2, pipeline_id))
thread1.start(); thread2.start()
thread1.join();  thread2.join()
```

Problemas:

- **Sem ganho**: as threads são criadas e imediatamente aguardadas (`join`), então a
  execução é sequencial na prática, só com o custo de criar/destruir 2 threads de SO por
  iteração.
- **Não é thread-safe**: `QgsSpatialIndex`, `QgsGeometry` e acesso ao *data provider* não
  podem ser usados concorrentemente. Isso pode travar o QGIS de forma intermitente.
- **Condição de corrida**: `_list_valves`, `_q_list_pipelines`, etc. são mutados pelas duas
  threads sem lock.

**Correção:** remover o `threading` e chamar direto:

```python
self.__find_neighbors(v1, pipeline_id)
self.__find_neighbors(v2, pipeline_id)
```

Se um dia quiser paralelismo real, use `QgsTask` subtarefas ou `concurrent.futures` sobre
dados imutáveis — não threads compartilhando o índice.

---

## 3. `_get_pipeline_dn` faz uma consulta ao provider por chamada — CRÍTICO

```python
def _get_pipeline_dn(self, pipeline_id):
    return list(self._pipelines_features.getFeatures([pipeline_id]))[0]['diametro_nominal']
```

Cada chamada é uma requisição ao provider (shapefile/PostGIS = round-trip de I/O). E em
`__find_pipelines_neighbors` isso é chamado **dentro do loop dos 4 vizinhos**, refazendo a
consulta do diâmetro de origem 4 vezes por vértice.

**Correções:**

1. Calcular `origin_diameter` uma única vez, fora do `for`:
   ```python
   origin_diameter = self._get_pipeline_dn(pipeline_origin_id) if pipeline_origin_id else None
   for pipeline_id in pipelines_nearest:
       ...
   ```
2. Cachear os diâmetros num dicionário preenchido de uma vez só:
   ```python
   req = QgsFeatureRequest().setSubsetOfAttributes(['diametro_nominal'], self._pipelines_features.fields())
   self._dn_by_id = {f.id(): f['diametro_nominal'] for f in self._pipelines_features.getFeatures(req)}
   ```
   Depois `self._dn_by_id[pipeline_id]` — O(1), sem I/O.
3. Se preferir consulta pontual, use `layer.getFeature(id)` em vez de
   `list(getFeatures([id]))[0]`.

---

## 4. Fila com geometrias duplicadas e estrutura redundante — ALTO

- `_q_list_pipelines` (deque de `QgsGeometry`) e `_q_list_pipelines_ids` são mantidos em
  paralelo. Como o índice já usa `FlagStoreFeatureGeometries`, basta enfileirar **ids** e
  obter a geometria via `self.__idx_pipelines.geometry(id)` quando for processar. Menos
  memória e menos cópias de geometria.
- Vizinhos são adicionados à fila sem checar se **já estão na fila** (só se checa
  `_list_visited_pipelines_ids`). O mesmo pipeline pode ser enfileirado várias vezes →
  trabalho redundante. Mantenha um `set` de "enfileirados" ou cheque
  `if pid not in self._list_visited_pipelines_ids and pid not in queued`.
- `_list_visited_pipelines` (set de geometrias) nunca é usado de forma útil — só o set de
  ids importa em `finished()`. Pode ser removido inteiro.

---

## 5. `finished()` — múltiplos `selectByIds` + varredura de atributos — ALTO

```python
self._valves_features.selectByIds(list(self._list_valves_not_visible))
names_valves_not_visible = [feat['codigo'] for feat in self._valves_features.selectedFeatures()]
self._valves_features.selectByIds(list(self._list_valves_closed))
...
```

Cada `selectByIds` dispara repintura do canvas e dos painéis. São 4 seleções seguidas na
mesma camada só para traduzir id → `codigo`.

**Correção:** buscar os códigos com uma única requisição, sem mexer na seleção:

```python
all_ids = self._list_valves | self._list_valves_closed | self._list_valves_not_visible
req = QgsFeatureRequest().setFilterFids(list(all_ids)) \
        .setSubsetOfAttributes(['codigo'], self._valves_features.fields())
codigo_by_id = {f.id(): f['codigo'] for f in self._valves_features.getFeatures(req)}
```

E fazer **um único** `selectByIds` no fim, com o conjunto que deve ficar realçado.

---

## 6. `QgsMessageLog.logMessage` dentro dos loops quentes — ALTO

Há log por iteração, por vértice e por vizinho (`f'Iteration {n}'`, `f'|---> Valve
Nearest...'`, etc.). O painel de Log do QGIS é surpreendentemente caro e ainda força
formatação de f-string mesmo quando ninguém olha.

**Correção:** condicionar ao modo debug e/ou acumular um resumo:

```python
if self.debug:
    QgsMessageLog.logMessage(..., 'TracingCAJ', Qgis.Info)
```

Trocar todos os `print(...)` remanescentes por log condicional também.

---

## 7. `FindPoints.get_points` — subdivisão O(n²) — ALTO

```python
while True:
    if breakForce == 1000: break
    ...
    pipeline = QgsGeometry.fromMultiPointXY(pipe)   # reconstrói a geometria inteira a cada passe
    for i in range(len(pipe) - 1):
        d = QgsDistanceArea()                       # instanciado por segmento
        distance = d.measureLine(...)
        if distance > 10:
            self.split_line(...)                    # insere 1 ponto no meio
```

O laço externo repete até **1000 vezes**, e a cada passe só divide segmentos ao meio,
reconstruindo toda a geometria. Um segmento de 100 m leva ~4 passes; o custo total é
quadrático no número de vértices.

**Correções:**

- Criar `QgsDistanceArea` **uma vez** fora dos laços (e configurar `setEllipsoid`/CRS uma
  vez).
- Densificar em **um único passe** com a API pronta:
  `geom.densifyByDistance(10)` — resolve o objetivo (nenhum segmento > 10 m) sem laço.
- `distances` é recriada/`clear()` a cada iteração; com a abordagem acima some.

---

## 8. `list` usada como conjunto — O(n²) — MÉDIO

- `FindPoints.find_hds_by_nearest_neighbor`: `if hd not in self.list_hds` sobre uma lista.
  Use `self.list_hds = set()` e converta para lista só no `finished()`.
- `FindPoints.run()` faz `self.q_list_pipelines.pop(0)` — remoção no início de lista é O(n).
  Use `collections.deque` e `popleft()`.

---

## 9. `LancamentoRamal` — bugs que impedem execução + O(n²) — MÉDIO

- `find_nearest_pipelines` usa `self.idx_pipelines`, mas o atributo criado é
  `self.__idx_pipelines` (name mangling) → `AttributeError` na primeira chamada.
- `finished()` referencia `self.__list_valves`, `self.__iterations`,
  `self.__list_visited_pipelines_ids`, `self.__exception` que nunca são definidos.
- `run()` não retorna `True/False` (a `QgsTask` espera bool).
- `points_features.index(p)` dentro do `for p in points_features` → O(n²). Use
  `for i, p in enumerate(points_features)`.
- Índice espacial no `__init__` (ver item 1).

---

## 10. Itens menores / portabilidade

- `view/__init__.py`: `r'ui\config_dialog.ui'` com barra invertida — quebra em Linux/macOS.
  Use `os.path.join('ui', 'config_dialog.ui')`.
- `controller.layerSelectionValves` lê `self._ui.layer_pipelines.itemData(index)` em vez de
  `self._ui.layer_valves...` — seleciona a camada errada.
- `controller.layerSelectionPipeline` fixa
  `QgsProject.instance().mapLayersByName('valves_tracing')` (nome fixo, retorna lista) —
  contorna a combo de seleção.
- `TracingPipelines.__init__`: o `if self.__idx_valves is None ...` logo após atribuir
  `None` é sempre verdadeiro; simplificar.
- `base64` importado e não usado em `controller/__init__.py`.
- `tracing.py._set_info_button` adiciona o ícone à toolbar, e `initGui` adiciona de novo —
  botão duplicado.
- Sem `.py` de testes nem `requirements`/CI; difícil medir regressões de performance.

---

## Prioridade sugerida

| # | Item | Esforço | Impacto |
|---|------|---------|---------|
| 1 | Índice espacial → `run()` | baixo | alto (trava a GUI) |
| 2 | Remover `threading` | baixo | alto (crash + custo) |
| 3 | Cache de `diametro_nominal` | baixo | alto (I/O por nó) |
| 5 | `finished()` sem múltiplos `selectByIds` | baixo | médio-alto |
| 6 | Log condicional ao debug | baixo | médio-alto |
| 7 | `densifyByDistance` em vez do laço | médio | alto (em `FindPoints`) |
| 4 | Fila só de ids + dedupe | médio | médio |
| 8 | `set` no lugar de `list` | baixo | médio |
| 9 | Corrigir `LancamentoRamal` | médio | (hoje não roda) |
