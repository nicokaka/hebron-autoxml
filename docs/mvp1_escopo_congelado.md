# Escopo Congelado do HebronAutoXML (MVP 1)

Este documento registra o alinhamento definitivo do produto. Nenhum código do MVP 1 será iniciado antes dos resultados reais da Etapa 0.

## O MVP 1 Real
Um aplicativo desktop simples para Windows, com interface gráfica mínima, focado em facilitar o trabalho da equipe de contabilidade.

## O que entra no MVP 1
1. Seleção simples de empresa e certificado digital (A1).
2. Importação manual do arquivo Excel do sistema.
3. Leitura da coluna B para extração das chaves de acesso.
4. Validação das chaves (44 dígitos) e filtro de duplicadas.
5. Download dos XMLs consultando os webservices da SEFAZ.
6. Geração de relatório de status em formato Excel.
7. Distribuição via arquivo executável autônomo (.exe).

## O que NÃO entra no MVP 1
- Automação em background ou tarefas agendadas.
- Dashboards e estatísticas.
- Banco de dados de qualquer tipo.
- Histórico ou logs complexos para o usuário.
- Múltiplas telas de configuração.

## Regra do CT-e
- Se a Etapa 0 comprovar que a consulta de CT-e direto pela chave funciona sem atrito: **Entra no MVP 1**.
- Se a consulta gerar erros de webservice ou bloquear a operação por chave: **Fica adiado para o MVP 1.1**.

## Regra da Manifestação do Destinatário
- Se a SEFAZ fornecer apenas o resumo da nota (`resNFe`): **O envio da manifestação do destinatário entra no MVP 1**.
- Se a SEFAZ entregar o XML completo diretamente (`procNFe`): **A manifestação do destinatário não entra no MVP 1**.
