from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from mapa_bairros import (
    carregar_bairros_geodf,
    construir_mapa_bairros_inct,
    normalizar_nome_bairro,
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
def obter_geodf_bairros(caminho_gpkg: str, caminho_csv: str):
    return carregar_bairros_geodf(Path(caminho_gpkg), Path(caminho_csv))


def formatar_inteiro(valor: float | int) -> str:
    return f"{int(round(valor)):,}".replace(",", ".")


def formatar_percentual(valor: float) -> str:
    return f"{valor:.2f}%".replace(".", ",")


def main():
    if not CAMINHO_CSV_LIMPO.exists():
        st.error(f"Arquivo CSV não encontrado em: {CAMINHO_CSV_LIMPO}")
        st.stop()

    if not CAMINHO_GPKG_SETORES.exists():
        st.error(f"Arquivo GeoPackage não encontrado em: {CAMINHO_GPKG_SETORES}")
        st.stop()

    df_completo = carregar_dados_csv(str(CAMINHO_CSV_LIMPO))
    gdf_bairros = obter_geodf_bairros(
        str(CAMINHO_GPKG_SETORES), str(CAMINHO_CSV_LIMPO)
    )

    lista_bairros = gdf_bairros["nome_exibicao"].tolist()

    # ==========================================================
    # BARRA LATERAL ESQUERDA (Informações / Busca por Bairro)
    # ==========================================================
    with st.sidebar:
        st.header("Informações")
        st.caption("Busca territorial — Porto Alegre / RS")

        st.text_input("País*", value="Brazil", disabled=True)
        st.text_input("Estado*", value="Rio Grande do Sul", disabled=True)
        st.text_input("Cidade*", value="Porto Alegre", disabled=True)

        filtro_texto = st.text_input(
            "Filtrar bairro",
            placeholder="Ex.: Passo D'Areia",
        ).strip()

        if filtro_texto:
            chave_filtro = normalizar_nome_bairro(filtro_texto)
            opcoes_filtradas = [
                nome
                for nome in lista_bairros
                if chave_filtro in normalizar_nome_bairro(nome)
            ]
        else:
            opcoes_filtradas = lista_bairros

        if not opcoes_filtradas:
            st.warning("Nenhum bairro encontrado com esse filtro.")
            opcoes_filtradas = lista_bairros

        bairro_selecionado = st.radio(
            "Bairro",
            options=opcoes_filtradas,
            index=0,
        )

    chave_bairro_atual = normalizar_nome_bairro(bairro_selecionado)
    df_bairro = df_completo[df_completo["bairro_chave"] == chave_bairro_atual].copy()

    # ==========================================================
    # CABEÇALHO E BOTÃO DE NAVEGAÇÃO PARA A TELA 2
    # ==========================================================
    col_titulo, col_navegacao = st.columns([4, 1])

    with col_titulo:
        st.title("Tela 1 — Simulação de Inundação (INCT)")
        st.caption(
            f"{bairro_selecionado} · Divisão oficial dos 94 bairros de Porto Alegre "
            "(visualização territorial sem filtro de nível)"
        )

    with col_navegacao:
        st.write("")
        st.link_button("Ir para Tela 2 →", URL_TELA_2, use_container_width=True)

    # ==========================================================
    # CORPO PRINCIPAL: MAPA DE BAIRROS + PAINEL DIREITO (INCT)
    # ==========================================================
    col_mapa, col_controles = st.columns([3.3, 1.2], gap="medium")

    with col_mapa:
        mapa_bairros = construir_mapa_bairros_inct(
            gdf_bairros=gdf_bairros,
            bairro_selecionado=bairro_selecionado,
        )
        st_folium(
            mapa_bairros,
            use_container_width=True,
            height=540,
            returned_objects=[],
        )

    with col_controles:
        st.subheader("Nível d'água (3,0 - 10,0 m)")
        st.caption("Controles visuais (ainda não aplicados ao mapa)")

        if "nivel_agua_ui" not in st.session_state:
            st.session_state["nivel_agua_ui"] = 10.0

        nivel_escolhido = st.number_input(
            "Nível da água (m)",
            min_value=3.0,
            max_value=10.0,
            step=0.1,
            key="nivel_agua_ui",
        )

        btn_col1, btn_col2, btn_col3 = st.columns(3)
        with btn_col1:
            if st.button("3.0", use_container_width=True):
                st.session_state["nivel_agua_ui"] = 3.0
                st.rerun()
        with btn_col2:
            if st.button("5.3", use_container_width=True):
                st.session_state["nivel_agua_ui"] = 5.3
                st.rerun()
        with btn_col3:
            if st.button("10.0", use_container_width=True):
                st.session_state["nivel_agua_ui"] = 10.0
                st.rerun()

        st.divider()

        st.subheader("Tamanho da via: 0.0002")
        st.number_input(
            "Tamanho da via",
            min_value=0.0001,
            max_value=0.0100,
            value=0.0002,
            step=0.0001,
            format="%.4f",
        )

        st.checkbox("Alterar estilo do mapa", value=False)

        st.divider()
        st.subheader("Histórico do nível d'água")
        st.caption("Dados de nível indisponíveis no momento.")

    # ==========================================================
    # RODAPÉ DE INDICADORES DO BAIRRO SELECIONADO
    # ==========================================================
    st.divider()

    linha_bairro = gdf_bairros[
        gdf_bairros["bairro_chave"] == chave_bairro_atual
    ].iloc[0]

    total_edificacoes = int(linha_bairro["edificacoes_totais"])
    populacao_total = int(linha_bairro["populacao_total"])
    max_edificacoes_afetadas = int(linha_bairro["max_edificacoes_afetadas"])
    max_populacao_afetada = int(linha_bairro["max_populacao_afetada"])
    max_percentual_afetado = float(linha_bairro["max_percentual_afetado"])

    col_info1, col_info2, col_info3 = st.columns(3)

    with col_info1:
        st.markdown("**Informações de edificações na área selecionada**")
        st.write(f"Total de edificações: **{formatar_inteiro(total_edificacoes)}**")
        st.write(
            f"Máx. edificações afetadas (cenário 10 m): **{formatar_inteiro(max_edificacoes_afetadas)}**"
        )
        st.write(
            f"Máx. percentual afetado: **{formatar_percentual(max_percentual_afetado)}**"
        )

    with col_info2:
        st.markdown("**População (Censo 2022)**")
        st.write(f"População total: **{formatar_inteiro(populacao_total)}**")
        st.write(
            f"Máx. população afetada (cenário 10 m): **{formatar_inteiro(max_populacao_afetada)}**"
        )

    with col_info3:
        st.markdown("**Resumo do arquivo CSV para o bairro**")
        st.write(f"Registros de níveis disponíveis: **{len(df_bairro)}**")
        if not df_bairro.empty:
            nivel_min = df_bairro["nivel_m"].min()
            nivel_max = df_bairro["nivel_m"].max()
            st.write(f"Faixa de cotas: **{nivel_min:.1f} m a {nivel_max:.1f} m**")


if __name__ == "__main__":
    main()