import shutil
import os

def gerar_zip_arquivos(pasta_origem: str, caminho_zip_saida: str):
    """
    Compacta um diretório no formato .zip e salva no destino.
    """
    
    # O make_archive já acopla '.zip'
    shutil.make_archive(caminho_zip_saida, 'zip', pasta_origem)
