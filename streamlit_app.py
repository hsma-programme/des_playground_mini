import streamlit as st

pg = st.navigation(
    [
        st.Page("app_model.py"),
    ],
)

pg.run()
