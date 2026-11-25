from pathlib import Path
import re
import sqlite3
import unicodedata

import folium
import geopandas as gpd
import pandas as pd
from shapely import wkb
from shapely.ops import unary_union


PALETA_BAIRROS = [
    "#4e79a7",  # azul aço
    "#59a14f",  # verde folha
    "#edc948",  # amarelo suave
    "#e15759",  # coral/vermelho
    "#76b7b2",  # verde-água / teal
    "#f28e2b",  # laranja/âmbar
    "#b07aa1",  # lilás/roxo
    "#9c755f",  # marrom suave
    "#8cd17d",  # verde claro
    "#ff9da7",  # rosa suave
]


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


def carregar_bairros_geodf(
    caminho_gpkg: Path,
    caminho_csv: Path,
    tolerancia_simplificacao: float = 0.00008,
) -> gpd.GeoDataFrame:
    """Dissolve os setores de Porto Alegre por bairro e une métricas de data_limpo.csv."""
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

    df_csv = pd.read_csv(caminho_csv)
    df_csv["bairro_chave"] = df_csv["bairro"].apply(normalizar_nome_bairro)

    metricas_por_bairro = (
        df_csv.groupby(["bairro", "bairro_chave"], as_index=False)
        .agg(
            populacao_total=("population", "max"),
            edificacoes_totais=("total_buildings", "max"),
            max_edificacoes_afetadas=("affected_buildings", "max"),
            max_populacao_afetada=("affected_population", "max"),
            max_percentual_afetado=("percentage", "max"),
        )
    )

    gdf_final = gdf_bairros.merge(metricas_por_bairro, on="bairro_chave", how="left")
    gdf_final["nome_exibicao"] = gdf_final["bairro"].fillna(gdf_final["bairro_mapa"])
    gdf_final["populacao_total"] = gdf_final["populacao_total"].fillna(0).astype(int)
    gdf_final["edificacoes_totais"] = gdf_final["edificacoes_totais"].fillna(0).astype(int)
    gdf_final["max_edificacoes_afetadas"] = (
        gdf_final["max_edificacoes_afetadas"].fillna(0).astype(int)
    )
    gdf_final["max_populacao_afetada"] = (
        gdf_final["max_populacao_afetada"].fillna(0).astype(int)
    )
    gdf_final["max_percentual_afetado"] = (
        gdf_final["max_percentual_afetado"].fillna(0.0).round(2)
    )

    gdf_ordenado = gdf_final.sort_values("nome_exibicao").reset_index(drop=True)
    gdf_ordenado["cor_bairro"] = [
        PALETA_BAIRROS[i % len(PALETA_BAIRROS)] for i in range(len(gdf_ordenado))
    ]
    return gdf_ordenado


def construir_mapa_bairros_inct(
    gdf_bairros: gpd.GeoDataFrame,
    bairro_selecionado: str | None = None,
    estilo_ruas_claro: bool = True,
) -> folium.Map:
    """Cria o mapa Folium com ruas visíveis, cores por bairro e destaque da seleção."""
    chave_selecionada = normalizar_nome_bairro(bairro_selecionado)

    mapa = folium.Map(
        location=[-30.065, -51.185],
        zoom_start=12,
        tiles=None,
        control_scale=True,
    )

    # Camada base principal: OpenStreetMap (ruas, quadras e pontos de referência sem API key)
    folium.TileLayer(
        tiles="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr="&copy; OpenStreetMap contributors",
        name="Ruas (OpenStreetMap)",
        max_zoom=19,
        show=estilo_ruas_claro,
    ).add_to(mapa)

    # Camada base alternativa: Esri World Street Map (estilo cartográfico limpo, sem API key)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles &copy; Esri",
        name="Mapa Cartográfico (Esri)",
        max_zoom=19,
        show=not estilo_ruas_claro,
    ).add_to(mapa)

    gdf_nao_selecionados = gdf_bairros[
        gdf_bairros["bairro_chave"] != chave_selecionada
    ].copy()
    gdf_selecionado = gdf_bairros[
        gdf_bairros["bairro_chave"] == chave_selecionada
    ].copy()

    # Camada multicolorida para todos os bairros (deixando as ruas bem legíveis por baixo)
    if not gdf_nao_selecionados.empty:
        folium.GeoJson(
            gdf_nao_selecionados.__geo_interface__,
            name="Bairros de Porto Alegre",
            style_function=lambda feature: {
                "fillColor": feature["properties"].get("cor_bairro", "#76b7b2"),
                "color": "#1f2937",
                "weight": 1.3,
                "fillOpacity": 0.24,
            },
            highlight_function=lambda feature: {
                "fillColor": feature["properties"].get("cor_bairro", "#f28e2b"),
                "color": "#0f172a",
                "weight": 2.4,
                "fillOpacity": 0.42,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=[
                    "nome_exibicao",
                    "populacao_total",
                    "edificacoes_totais",
                    "max_populacao_afetada",
                    "max_percentual_afetado",
                ],
                aliases=[
                    "Bairro:",
                    "População (2022):",
                    "Total de edificações:",
                    "Máx. pop. afetada:",
                    "Máx. % afetado:",
                ],
                localize=True,
                sticky=True,
            ),
        ).add_to(mapa)

    # Camada destacada do bairro selecionado
    if not gdf_selecionado.empty:
        folium.GeoJson(
            gdf_selecionado.__geo_interface__,
            name="Bairro selecionado",
            style_function=lambda _: {
                "fillColor": "#2563eb",
                "color": "#1e3a8a",
                "weight": 3.0,
                "fillOpacity": 0.36,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=[
                    "nome_exibicao",
                    "populacao_total",
                    "edificacoes_totais",
                    "max_populacao_afetada",
                    "max_percentual_afetado",
                ],
                aliases=[
                    "Bairro selecionado:",
                    "População (2022):",
                    "Total de edificações:",
                    "Máx. pop. afetada:",
                    "Máx. % afetado:",
                ],
                localize=True,
                sticky=True,
            ),
        ).add_to(mapa)

        min_lon, min_lat, max_lon, max_lat = gdf_selecionado.total_bounds
        mapa.fit_bounds([[min_lat, min_lon], [max_lat, max_lon]], padding=(28, 28))

    legenda_html = """
    <div style="
        position: fixed;
        bottom: 24px;
        right: 16px;
        z-index: 9999;
        background: rgba(255, 255, 255, 0.95);
        color: #111827;
        padding: 10px 12px;
        border-radius: 6px;
        border: 1px solid #cbd5e1;
        font-size: 12px;
        line-height: 1.55;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    ">
        <div style="font-weight: 700; margin-bottom: 4px;">Legenda do mapa</div>
        <div><span style="display:inline-block;width:12px;height:12px;background:rgba(37,99,235,0.40);border:2px solid #1e3a8a;margin-right:6px;"></span>Área selecionada</div>
        <div><span style="display:inline-block;width:12px;height:12px;background:rgba(118,183,178,0.40);border:1.5px solid #1f2937;margin-right:6px;"></span>Demarcação dos bairros (POA)</div>
        <div style="color:#475569;font-size:11px;margin-top:2px;">Base viária: OpenStreetMap / Esri</div>
    </div>
    """
    mapa.get_root().html.add_child(folium.Element(legenda_html))
    folium.LayerControl(position="topleft").add_to(mapa)

    return mapa