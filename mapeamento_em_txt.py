import os
from datetime import datetime

def mapear_projeto(diretorio_base, nome_arquivo):
    # Itens a serem ignorados
    ignorar_diretorios = ['venv', '__pycache__', 'node_modules', '.git', '.idea', 'staticfiles', '.vscode']
    ignorar_arquivos = ['.env', 'package-lock.json', 'db.sqlite3', 'Mapeamento_', 'test_upload.txt']

    # Caminho do arquivo para salvar o mapeamento
    caminho_arquivo = os.path.join(diretorio_base, nome_arquivo)

    with open(caminho_arquivo, 'w', encoding='utf-8') as arquivo:
        for raiz, diretorios, arquivos in os.walk(diretorio_base):
            # Remover os diretórios a serem ignorados
            diretorios[:] = [d for d in diretorios if d not in ignorar_diretorios]

            # Ignorar diretórios específicos
            if any(ignorado in raiz for ignorado in ignorar_diretorios):
                continue

            # Escrever o nome do diretório
            arquivo.write(f"Diretório: {os.path.relpath(raiz, diretorio_base)}\n")

            # Listar arquivos dentro do diretório
            for nome_arquivo in arquivos:
                if any(nome_arquivo.startswith(prefixo) for prefixo in ignorar_arquivos):
                    continue
                arquivo.write(f"  - {nome_arquivo}\n")

            arquivo.write("\n")

    # Abrir o arquivo após salvar
    os.startfile(caminho_arquivo)

if __name__ == "__main__":
    # Diretório base do projeto
    diretorio_base = os.path.dirname(os.path.abspath(__file__))

    # Nome do arquivo com a data atual
    nome_arquivo = f"Mapeamento_{datetime.now().strftime('%d-%m-%H-%M')}.txt"

    mapear_projeto(diretorio_base, nome_arquivo)
