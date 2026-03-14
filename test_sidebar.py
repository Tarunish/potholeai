import streamlit as st
st.markdown("""
<style>
    section[data-testid="stSidebar"] { display: flex !important; }
</style>
""", unsafe_allow_html=True)
st.sidebar.write("Hello")
st.title("Sidebar Test")
