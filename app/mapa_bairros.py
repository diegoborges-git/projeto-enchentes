"""
Utilizei IA no desenvolvimento desse módulo, para a criação do dashboard com Streamlit. 
Pietro utilizou HTML e CSS, mas eu não tenho tais habilidades.
"""
from pathlib import Path
import re
import sqlite3
import unicodedata

import folium
import geopandas as gpd
import matplotlib.colors as mcolors
import pandas as pd
from shapely import wkb
from shapely.ops import unary_union


CORES_AMBAR_RUBI = ["#fef9c3", "#fde047", "#f59e0b", "#ea580c", "#991b1b"]
CMAP_AMBAR_RUBI = mcolors.LinearSegmentedColormap.from_list(
    "ambar_a_rubi", CORES_AMBAR_RUBI
)
GRADIENTE_VERTICAL_CSS = f"linear-gradient(180deg, {', '.join(reversed(CORES_AMBAR_RUBI))})"


def cor_por_percentual_gradual(pct: float) -> str:
    """Calcula cor contínua na escala Âmbar a Rubi conforme a porcentagem afetada (0 a 100)."""
    pct_limpo = max(0.0, min(100.0, float(pct)))
    if pct_limpo <= 0.0:
        return "#94a3b8"
    t = 0.12 + 0.88 * (pct_limpo / 100.0)
    return mcolors.to_hex(CMAP_AMBAR_RUBI(min(1.0, max(0.0, t))))


def normalizar_nome_bairro(texto: object) -> str:
    """Padroniza nomes de bairros para cruzar CSV e GeoPackage com segurança."""
    if texto is None or pd.isna(texto):
        return ""
    texto_limpo = str(texto).strip().lower()
    texto_sem_acento = unicodedata.normalize("NFKD", texto_limpo)
    texto_ascii = "".join(
        caractere for caractere in texto_sem_acento if not unicodedata.combining(caractere)
    )
    return re.sub(r"[^a-z0-9]+", " ", texto_ascii).strip()


def _ler_geometria_gpkg(blob_geom: bytes | None):
    """Extrai o WKB de um blob GeoPackage e converte para geometria Shapely."""
    if blob_geom is None or len(blob_geom) < 8:
        return None
    flags = blob_geom[3]
    codigo_envelope = (flags >> 1) & 0x07
    tamanhos_envelope = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}
    offset_wkb = 8 + tamanhos_envelope.get(codigo_envelope, 0)
    return wkb.loads(blob_geom[offset_wkb:])


def carregar_bairros_base_geodf(
    caminho_gpkg: Path,
    tolerancia_simplificacao: float = 0.00008,
) -> gpd.GeoDataFrame:
    """Carrega e dissolve os setores censitários de Porto Alegre por bairro."""
    conexao = sqlite3.connect(caminho_gpkg)
    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT NM_BAIRRO, geom
            FROM RS_setores_CD2022
            WHERE NM_MUN = 'Porto Alegre' AND NM_BAIRRO IS NOT NULL
            """
        )
        linhas_setores = cursor.fetchall()
    finally:
        conexao.close()

    registros_setores = []
    for nome_bairro_gpkg, blob_geom in linhas_setores:
        geometria = _ler_geometria_gpkg(blob_geom)
        if geometria is not None and not geometria.is_empty:
            registros_setores.append(
                {
                    "nome_bairro_gpkg": nome_bairro_gpkg,
                    "geometria": geometria.buffer(0),
                }
            )

    df_setores = pd.DataFrame(registros_setores)
    bairros_dissolvidos = []

    for nome_bairro, grupo in df_setores.groupby("nome_bairro_gpkg"):
        geometria_unida = unary_union(grupo["geometria"].tolist()).buffer(0)
        geometria_simplificada = geometria_unida.simplify(
            tolerancia_simplificacao, preserve_topology=True
        )
        bairros_dissolvidos.append(
            {
                "bairro_mapa": nome_bairro,
                "bairro_chave": normalizar_nome_bairro(nome_bairro),
                "geometry": geometria_simplificada,
            }
        )

    gdf_bairros = gpd.GeoDataFrame(bairros_dissolvidos, crs="EPSG:4326")
    return gdf_bairros.sort_values("bairro_mapa").reset_index(drop=True)


def _agragar_nivel_csv(df_csv: pd.DataFrame, nivel_efetivo: float) -> pd.DataFrame:
    """Agrega os dados de data_limpo.csv para um nível específico (em metros)."""
    df_nivel = df_csv[df_csv["nivel_m"].round(1) == round(float(nivel_efetivo), 1)].copy()
    if df_nivel.empty:
        return pd.DataFrame(
            columns=[
                "bairro_chave",
                "bairro_csv",
                "populacao_total",
                "edificacoes_totais",
                "edificacoes_afetadas",
                "populacao_afetada",
                "percentual_afetado",
            ]
        )

    return df_nivel.groupby("bairro_chave", as_index=False).agg(
        bairro_csv=("bairro", "first"),
        populacao_total=("population", "max"),
        edificacoes_totais=("total_buildings", "max"),
        edificacoes_afetadas=("affected_buildings", "max"),
        populacao_afetada=("affected_population", "max"),
        percentual_afetado=("percentage", "max"),
    )


def obter_resumo_cidade_nivel(df_csv: pd.DataFrame, nivel_m: float) -> dict:
    """Retorna os indicadores gerais de Porto Alegre para o nível selecionado."""
    niveis_disponiveis = sorted(df_csv["nivel_m"].dropna().round(1).unique())
    nivel_efetivo = (
        float(min(niveis_disponiveis, key=lambda x: abs(float(x) - float(nivel_m))))
        if len(niveis_disponiveis) > 0
        else float(nivel_m)
    )
    df_niv = _agragar_nivel_csv(df_csv, nivel_efetivo)
    if df_niv.empty:
        return {
            "nivel_efetivo": nivel_efetivo,
            "populacao_afetada": 0,
            "edificacoes_afetadas": 0,
            "bairros_atingidos": 0,
            "total_bairros": 0,
            "df_nivel": df_niv,
        }

    bairros_atingidos = int(
        ((df_niv["edificacoes_afetadas"] > 0) | (df_niv["populacao_afetada"] > 0)).sum()
    )
    return {
        "nivel_efetivo": nivel_efetivo,
        "populacao_afetada": int(round(df_niv["populacao_afetada"].sum())),
        "edificacoes_afetadas": int(round(df_niv["edificacoes_afetadas"].sum())),
        "bairros_atingidos": bairros_atingidos,
        "total_bairros": int(len(df_niv)),
        "df_nivel": df_niv,
    }


def obter_curva_populacao_cidade(df_csv: pd.DataFrame) -> pd.DataFrame:
    """Calcula a população e edificações afetadas na cidade para cada nível de 3,0 m a 10,0 m."""
    if df_csv.empty:
        return pd.DataFrame(
            columns=["nivel_m", "populacao_afetada", "edificacoes_afetadas", "bairros_atingidos"]
        )

    niveis = sorted(df_csv["nivel_m"].dropna().round(1).unique())
    linhas = []
    for n in niveis:
        res = obter_resumo_cidade_nivel(df_csv, float(n))
        linhas.append(
            {
                "nivel_m": float(n),
                "populacao_afetada": res["populacao_afetada"],
                "edificacoes_afetadas": res["edificacoes_afetadas"],
                "bairros_atingidos": res["bairros_atingidos"],
            }
        )
    return pd.DataFrame(linhas)


def aplicar_nivel_aos_bairros(
    gdf_base: gpd.GeoDataFrame,
    df_csv: pd.DataFrame,
    nivel_m: float,
) -> gpd.GeoDataFrame:
    """Cruza a geometria dos bairros com os dados de data_limpo.csv no nivel_m escolhido."""
    niveis_disponiveis = sorted(df_csv["nivel_m"].dropna().unique())
    if not niveis_disponiveis:
        nivel_efetivo = float(nivel_m)
        df_nivel_agg = _agragar_nivel_csv(df_csv.iloc[0:0], nivel_efetivo)
    else:
        nivel_efetivo = min(
            niveis_disponiveis, key=lambda x: abs(float(x) - float(nivel_m))
        )
        df_nivel_agg = _agragar_nivel_csv(df_csv, float(nivel_efetivo))

    gdf_niv = gdf_base.merge(df_nivel_agg, on="bairro_chave", how="left")
    gdf_niv["nome_exibicao"] = gdf_niv["bairro_csv"].fillna(gdf_niv["bairro_mapa"])
    gdf_niv["nivel_aplicado"] = round(float(nivel_efetivo), 1)
    gdf_niv["populacao_total"] = gdf_niv["populacao_total"].fillna(0).astype(int)
    gdf_niv["edificacoes_totais"] = gdf_niv["edificacoes_totais"].fillna(0).astype(int)
    gdf_niv["edificacoes_afetadas"] = (
        gdf_niv["edificacoes_afetadas"].fillna(0).astype(int)
    )
    gdf_niv["populacao_afetada"] = gdf_niv["populacao_afetada"].fillna(0).round().astype(int)
    gdf_niv["percentual_afetado"] = gdf_niv["percentual_afetado"].fillna(0.0).round(2)
    gdf_niv["cor_nivel"] = gdf_niv["percentual_afetado"].apply(cor_por_percentual_gradual)

    return gdf_niv.sort_values("nome_exibicao").reset_index(drop=True)


def construir_mapa_bairros_inct(
    gdf_bairros: gpd.GeoDataFrame,
    bairro_selecionado: str | None = None,
    nivel_m: float = 5.3,
) -> folium.Map:
    """Cria o mapa Folium com gradiente Âmbar a Rubi, barra vertical e borda no selecionado."""
    chave_selecionada = normalizar_nome_bairro(bairro_selecionado)

    mapa = folium.Map(
        location=[-30.065, -51.185],
        zoom_start=12,
        tiles=None,
        control_scale=True,
    )

    folium.TileLayer(
        tiles="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr="&copy; OpenStreetMap contributors",
        name="Ruas (OpenStreetMap)",
        max_zoom=19,
        show=True,
    ).add_to(mapa)

    if not gdf_bairros.empty:
        folium.GeoJson(
            gdf_bairros.__geo_interface__,
            name="Bairros de Porto Alegre",
            style_function=lambda feature: {
                "fillColor": feature["properties"].get("cor_nivel", "#94a3b8"),
                "color": "#1e293b",
                "weight": 1.15,
                "fillOpacity": min(
                    0.78,
                    0.22
                    + (float(feature["properties"].get("percentual_afetado", 0.0)) / 100.0)
                    * 0.54,
                ),
            },
            highlight_function=lambda feature: {
                "fillColor": feature["properties"].get("cor_nivel", "#94a3b8"),
                "color": "#0f172a",
                "weight": 2.4,
                "fillOpacity": 0.82,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=[
                    "nome_exibicao",
                    "nivel_aplicado",
                    "percentual_afetado",
                    "edificacoes_afetadas",
                    "populacao_afetada",
                ],
                aliases=[
                    "Bairro:",
                    "Nível (m):",
                    "Porcentagem de prédios afetados:",
                    "Edif. afetadas:",
                    "Pop. afetada (est.):",
                ],
                localize=True,
                sticky=True,
            ),
        ).add_to(mapa)

    gdf_selecionado = gdf_bairros[
        gdf_bairros["bairro_chave"] == chave_selecionada
    ].copy()

    if not gdf_selecionado.empty:
        folium.GeoJson(
            gdf_selecionado.__geo_interface__,
            name="Bairro selecionado",
            style_function=lambda _: {
                "fillColor": "transparent",
                "color": "#0f172a",
                "weight": 4.2,
                "fillOpacity": 0.0,
            },
            interactive=False,
        ).add_to(mapa)

        min_lon, min_lat, max_lon, max_lat = gdf_selecionado.total_bounds
        mapa.fit_bounds([[min_lat, min_lon], [max_lat, max_lon]], padding=(28, 28))

    legenda_html = f"""
    <div style="
        position: fixed;
        bottom: 24px;
        right: 16px;
        z-index: 9999;
        background: rgba(255, 255, 255, 0.96);
        color: #111827;
        padding: 9px 11px;
        border-radius: 6px;
        border: 1px solid #cbd5e1;
        font-size: 11px;
        line-height: 1.35;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    ">
        <div style="font-weight: 700; margin-bottom: 6px; font-size: 12px;">
            Nível: {float(nivel_m):.1f} m
        </div>
        <div style="display: flex; align-items: center; margin-bottom: 8px;">
            <span style="
                display: inline-block;
                width: 12px;
                height: 12px;
                background: transparent;
                border: 3px solid #0f172a;
                margin-right: 6px;
                flex-shrink: 0;
            "></span>
            <span>Bairro selecionado</span>
        </div>
        <div style="display: flex; align-items: stretch; gap: 6px;">
            <div style="
                width: 12px;
                height: 92px;
                border-radius: 3px;
                border: 1px solid #94a3b8;
                background: {GRADIENTE_VERTICAL_CSS};
                flex-shrink: 0;
            "></div>
            <div style="
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                height: 92px;
                font-size: 10px;
                color: #334155;
            ">
                <span>100</span>
                <span>75</span>
                <span>50</span>
                <span>25</span>
                <span>0</span>
            </div>
        </div>
    </div>
    """
    mapa.get_root().html.add_child(folium.Element(legenda_html))

    return mapa