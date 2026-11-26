"""
Utilizei IA no desenvolvimento desse módulo, para a criação do dashboard com Streamlit. 
Pietro utilizou HTML e CSS, mas eu não tenho tais habilidades.
"""
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from mapa_bairros import (
    aplicar_nivel_aos_bairros,
    carregar_bairros_base_geodf,
    construir_mapa_bairros_inct,
    cor_por_percentual_gradual,
    normalizar_nome_bairro,
    obter_curva_populacao_cidade,
    obter_resumo_cidade_nivel,
)


st.set_page_config(
    page_title="Tela 1 — Simulação de Inundação (INCT)",
    layout="wide",
    initial_sidebar_state="expanded",
)


RAIZ_PROJETO = Path(__file__).resolve().parent.parent
CAMINHO_CSV_LIMPO = RAIZ_PROJETO / "dados" / "processados" / "data_limpo.csv"
CAMINHO_GPKG_SETORES = RAIZ_PROJETO / "dados" / "setores" / "RS_setores_CD2022.gpkg"
URL_TELA_2 = "http://localhost:8000/app/"
RECORD_MAIO_2024_M = 5.35
NIVEL_MIN_M = 3.0
NIVEL_MAX_M = 10.0
PASSO_NIVEL_M = 0.1


@st.cache_data
def carregar_dados_csv(caminho_csv: str) -> pd.DataFrame:
    df = pd.read_csv(caminho_csv)
    df["nivel_m"] = pd.to_numeric(df["nivel_m"], errors="coerce")
    df["affected_buildings"] = pd.to_numeric(
        df["affected_buildings"], errors="coerce"
    ).fillna(0)
    df["total_buildings"] = pd.to_numeric(
        df["total_buildings"], errors="coerce"
    ).fillna(0)
    df["percentage"] = pd.to_numeric(df["percentage"], errors="coerce").fillna(0.0)
    df["population"] = pd.to_numeric(df["population"], errors="coerce").fillna(0)
    df["affected_population"] = pd.to_numeric(
        df["affected_population"], errors="coerce"
    ).fillna(0)
    df["bairro_chave"] = df["bairro"].apply(normalizar_nome_bairro)
    return df


@st.cache_data
def obter_geodf_base_bairros(caminho_gpkg: str):
    return carregar_bairros_base_geodf(Path(caminho_gpkg))


@st.cache_data
def obter_curva_cache(df_csv: pd.DataFrame) -> pd.DataFrame:
    return obter_curva_populacao_cidade(df_csv)


def formatar_inteiro(valor: float | int) -> str:
    return f"{int(round(valor)):,}".replace(",", ".")


def formatar_percentual(valor: float) -> str:
    return f"{valor:.2f} por cento".replace(".", ",")


def _normalizar_nivel(valor: float) -> float:
    return max(NIVEL_MIN_M, min(NIVEL_MAX_M, round(float(valor), 1)))


def _aplicar_nivel_em_ambos(valor: float) -> None:
    nivel_limpo = _normalizar_nivel(valor)
    st.session_state["nivel_agua_slider"] = nivel_limpo
    st.session_state["nivel_agua_input"] = nivel_limpo


def definir_nivel_rapido(valor: float) -> None:
    _aplicar_nivel_em_ambos(valor)


def sincronizar_de_slider() -> None:
    _aplicar_nivel_em_ambos(st.session_state["nivel_agua_slider"])


def sincronizar_de_input() -> None:
    _aplicar_nivel_em_ambos(st.session_state["nivel_agua_input"])


def plotar_curva_populacao(df_curva: pd.DataFrame, nivel_atual: float) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    ax.plot(
        df_curva["nivel_m"],
        df_curva["populacao_afetada"],
        color="#2563eb",
        linewidth=2.3,
        label="População afetada",
    )
    ax.axvline(
        RECORD_MAIO_2024_M,
        color="#d97706",
        linestyle="--",
        linewidth=1.6,
        label=f"Maio/2024 ({RECORD_MAIO_2024_M:.2f} m)",
    )
    ax.axvline(
        nivel_atual,
        color="#0f766e",
        linestyle=":",
        linewidth=1.6,
        label=f"Cota atual ({nivel_atual:.1f} m)",
    )

    idx_prox = (df_curva["nivel_m"] - nivel_atual).abs().idxmin()
    row_prox = df_curva.loc[idx_prox]
    ax.scatter(
        [row_prox["nivel_m"]],
        [row_prox["populacao_afetada"]],
        color="#0f766e",
        zorder=5,
        s=45,
    )

    ax.set_xlabel("Nível do Guaíba (m)")
    ax.set_ylabel("População afetada")
    ax.grid(True, linestyle="--", alpha=0.35)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(loc="upper left", fontsize=8.5, frameon=False)
    fig.tight_layout()
    return fig


def plotar_pct_predios_bairros(
    df_nivel: pd.DataFrame,
    nivel_atual: float,
    bairro_selecionado: str,
) -> plt.Figure:
    atingidos = df_nivel[df_nivel["edificacoes_afetadas"] > 0].copy()
    atingidos = atingidos.sort_values("percentual_afetado", ascending=True)

    fig, ax = plt.subplots(
        figsize=(7.2, max(4.0, min(9.0, 0.28 * max(len(atingidos), 1))))
    )
    if atingidos.empty:
        ax.text(
            0.5,
            0.5,
            f"Nenhuma edificação atingida no nível {nivel_atual:.1f} m.",
            ha="center",
            va="center",
            fontsize=10,
        )
        ax.set_axis_off()
    else:
        top_plot = atingidos.tail(25).copy()
        cores_barras = [
            cor_por_percentual_gradual(v) for v in top_plot["percentual_afetado"]
        ]
        chave_sel = normalizar_nome_bairro(bairro_selecionado)
        bordas = [
            "#0f172a" if normalizar_nome_bairro(b) == chave_sel else "none"
            for b in top_plot["bairro_csv"]
        ]
        larguras_borda = [
            1.6 if normalizar_nome_bairro(b) == chave_sel else 0.0
            for b in top_plot["bairro_csv"]
        ]

        ax.barh(
            top_plot["bairro_csv"],
            top_plot["percentual_afetado"],
            color=cores_barras,
            edgecolor=bordas,
            linewidth=larguras_borda,
        )
        ax.set_xlabel("Porcentagem de prédios afetados")
        ax.set_xlim(0, max(100.0, float(top_plot["percentual_afetado"].max()) * 1.05))
        ax.grid(True, axis="x", linestyle="--", alpha=0.35)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    fig.tight_layout()
    return fig


def main():
    if not CAMINHO_CSV_LIMPO.exists():
        st.error(f"Arquivo CSV não encontrado em: {CAMINHO_CSV_LIMPO}")
        st.stop()

    if not CAMINHO_GPKG_SETORES.exists():
        st.error(f"Arquivo GeoPackage não encontrado em: {CAMINHO_GPKG_SETORES}")
        st.stop()

    if "nivel_agua_slider" not in st.session_state:
        st.session_state["nivel_agua_slider"] = 5.3
    if "nivel_agua_input" not in st.session_state:
        st.session_state["nivel_agua_input"] = _normalizar_nivel(
            st.session_state["nivel_agua_slider"]
        )

    nivel_atual = _normalizar_nivel(st.session_state["nivel_agua_slider"])

    df_completo = carregar_dados_csv(str(CAMINHO_CSV_LIMPO))
    gdf_base = obter_geodf_base_bairros(str(CAMINHO_GPKG_SETORES))
    df_curva = obter_curva_cache(df_completo)


    gdf_preview = aplicar_nivel_aos_bairros(
        gdf_base=gdf_base,
        df_csv=df_completo,
        nivel_m=nivel_atual,
    )
    lista_bairros = gdf_preview["nome_exibicao"].tolist()

    with st.sidebar:
        st.header("Informações")
        st.caption("Porto Alegre / RS")

        bairro_selecionado = st.selectbox(
            "Bairro",
            options=lista_bairros,
            index=0,
            key="bairro_selectbox",
            placeholder="Selecione ou digite um bairro...",
        )


    col_titulo, col_navegacao = st.columns([4, 1])
    with col_titulo:
        st.title("Tela 1 — Simulação de Inundação (INCT SiMAI)")
    with col_navegacao:
        st.write("")
        st.link_button("Ir para Tela 2 →", URL_TELA_2, use_container_width=True)


    col_slider, col_input, col_btn1, col_btn2, col_btn3 = st.columns(
        [3.6, 1.3, 0.9, 1.1, 0.9]
    )
    with col_slider:
        st.slider(
            "Nível do Guaíba (m)",
            min_value=NIVEL_MIN_M,
            max_value=NIVEL_MAX_M,
            step=PASSO_NIVEL_M,
            key="nivel_agua_slider",
            on_change=sincronizar_de_slider,
        )
    with col_input:
        st.number_input(
            "Cota (m)",
            min_value=NIVEL_MIN_M,
            max_value=NIVEL_MAX_M,
            step=PASSO_NIVEL_M,
            format="%.1f",
            key="nivel_agua_input",
            on_change=sincronizar_de_input,
        )
    with col_btn1:
        st.write("")
        st.button(
            "3,0 m",
            use_container_width=True,
            on_click=definir_nivel_rapido,
            args=(3.0,),
        )
    with col_btn2:
        st.write("")
        st.button(
            "5,3 m (2024)",
            use_container_width=True,
            on_click=definir_nivel_rapido,
            args=(5.3,),
        )
    with col_btn3:
        st.write("")
        st.button(
            "10,0 m",
            use_container_width=True,
            on_click=definir_nivel_rapido,
            args=(10.0,),
        )

    nivel_atual = _normalizar_nivel(st.session_state["nivel_agua_slider"])

    resumo_cidade = obter_resumo_cidade_nivel(df_completo, nivel_atual)
    gdf_bairros = aplicar_nivel_aos_bairros(
        gdf_base=gdf_base,
        df_csv=df_completo,
        nivel_m=nivel_atual,
    )

    kpi1, kpi2, kpi3 = st.columns(3)
    with kpi1:
        st.metric(
            "Pessoas afetadas (estimativa)",
            formatar_inteiro(resumo_cidade["populacao_afetada"]),
            help="Soma estimada da população afetada em Porto Alegre no nível selecionado.",
        )
    with kpi2:
        st.metric(
            "Prédios afetados",
            formatar_inteiro(resumo_cidade["edificacoes_afetadas"]),
            help="Soma de edificações afetadas nos bairros de Porto Alegre no nível selecionado.",
        )
    with kpi3:
        st.metric(
            "Bairros atingidos",
            f"{resumo_cidade['bairros_atingidos']} / {resumo_cidade['total_bairros']}",
            help="Quantidade de bairros com ao menos 1 edificação ou pessoa afetada no nível selecionado.",
        )

    st.divider()
    col_mapa, col_curva = st.columns([1.35, 1.0], gap="medium")

    chave_bairro_atual = normalizar_nome_bairro(bairro_selecionado)
    linha_bairro = gdf_bairros[gdf_bairros["bairro_chave"] == chave_bairro_atual].iloc[0]

    with col_mapa:
        st.subheader(
            f"Mapa de bairros por porcentagem de prédios afetados ({nivel_atual:.1f} m)"
        )
        mapa_bairros = construir_mapa_bairros_inct(
            gdf_bairros=gdf_bairros,
            bairro_selecionado=bairro_selecionado,
            nivel_m=nivel_atual,
        )
        st_folium(
            mapa_bairros,
            use_container_width=True,
            height=440,
            returned_objects=[],
        )

        # Informações do bairro logo abaixo do mapa (estilo INCT)
        info_edif, info_pop = st.columns(2)
        with info_edif:
            st.markdown(f"**Informações de edificações — {bairro_selecionado}**")
            st.write(
                f"Total de edificações: **{formatar_inteiro(linha_bairro['edificacoes_totais'])}**"
            )
            st.write(
                f"Edificações afetadas: **{formatar_inteiro(linha_bairro['edificacoes_afetadas'])}**"
            )
            st.write(
                f"Porcentagem afetada: **{formatar_percentual(linha_bairro['percentual_afetado'])}**"
            )

        with info_pop:
            st.markdown(f"**População (2022) — {bairro_selecionado}**")
            st.write(
                f"População total: **{formatar_inteiro(linha_bairro['populacao_total'])}**"
            )
            st.write(
                f"População afetada: **{formatar_inteiro(linha_bairro['populacao_afetada'])}**"
            )

    with col_curva:
        st.subheader("Curva da população afetada por nível do rio")
        fig_curva = plotar_curva_populacao(df_curva, nivel_atual)
        st.pyplot(fig_curva, use_container_width=True)
        plt.close(fig_curva)
        st.caption(
            f"Referência histórica: pico de maio de 2024 em {RECORD_MAIO_2024_M:.2f} m em Porto Alegre."
        )


    st.divider()
    col_barras, col_ranking = st.columns([1.15, 1.0], gap="medium")

    df_niv_tabela = resumo_cidade["df_nivel"].copy()

    with col_barras:
        st.subheader(
            f"Porcentagem de prédios afetados por bairro ({nivel_atual:.1f} m)"
        )
        fig_barras = plotar_pct_predios_bairros(
            df_niv_tabela,
            nivel_atual,
            bairro_selecionado=bairro_selecionado,
        )
        st.pyplot(fig_barras, use_container_width=True)
        plt.close(fig_barras)

    with col_ranking:
        st.subheader(f"Ranking dos bairros mais afetados ({nivel_atual:.1f} m)")
        criterio = st.selectbox(
            "Ordenar ranking por",
            options=[
                "Prédios afetados",
                "Porcentagem de prédios afetados",
                "População afetada (est.)",
            ],
            index=0,
        )
        mapa_col_ordenacao = {
            "Prédios afetados": "edificacoes_afetadas",
            "Porcentagem de prédios afetados": "percentual_afetado",
            "População afetada (est.)": "populacao_afetada",
        }
        col_ord = mapa_col_ordenacao[criterio]

        df_rank = df_niv_tabela.sort_values(
            by=[col_ord, "edificacoes_afetadas", "bairro_csv"],
            ascending=[False, False, True],
        ).reset_index(drop=True)
        df_rank.insert(0, "Posição", df_rank.index + 1)

        df_rank_exibir = pd.DataFrame(
            {
                "Pos.": df_rank["Posição"],
                "Bairro": df_rank["bairro_csv"],
                "Prédios afetados": df_rank["edificacoes_afetadas"].apply(formatar_inteiro),
                "Porcentagem de prédios": df_rank["percentual_afetado"].apply(
                    formatar_percentual
                ),
                "Pop. afetada (est.)": df_rank["populacao_afetada"].apply(formatar_inteiro),
            }
        )
        st.dataframe(
            df_rank_exibir.head(15),
            use_container_width=True,
            hide_index=True,
            height=410,
        )


if __name__ == "__main__":
    main()