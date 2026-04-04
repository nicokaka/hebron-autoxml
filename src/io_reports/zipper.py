import shutil
import os

def gerar_zip_arquivos(pasta_origem: str, caminho_zip_saida: str):
    """
    Zipa silenciosamente um repositório folder apontado. 
    A string 'caminho_zip_saida' não deve incluir a extensão '.zip', o python fará embutido.
    Ex: /tmp/nicolas/saida -> gera /tmp/nicolas/saida.zip
    """
    
    # O make_archive já acopla '.zip'
    shutil.make_archive(caminho_zip_saida, 'zip', pasta_origem)
