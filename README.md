Equipe: Diego Borges e Pietro Chies

Aplicação dividida em duas telas para visualização e simulação de cenários de inundação em Porto Alegre:
- Tela 2 (`app/server.py`): servidor web.
- Tela 1 (`app/tela1.py`):** painel interativo em Streamlit.


## Mapa dos impactos das enchentes

O painel exibe municípios do Rio Grande do Sul em um mapa interativo. Os círculos podem representar óbitos, população afetada ou pessoas desalojadas, e os pop-ups mostram os dados disponíveis de cada município.

### Executar

```bash
python3 app/server.py
```
Acesse http://localhost:8000.



## Tela 1
streamlit run app/tela1.py


## Como executar

Execute os comandos a partir da **raiz do projeto** (`projeto-enchentes`) em **dois terminais** (primeiro a Tela 2 e, em seguida, a Tela 1).

### 1. Preparar o ambiente Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt