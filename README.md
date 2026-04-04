# HebronAutoXML - Gate Técnico (Etapa 0)

Este diretório contempla a essência da **Etapa 0** do HebronAutoXML, com o intuito de estabelecer um veredito arquitetural sólido antes de investirmos tempo e código no MVP Completo (Front-end, banco de dados ou infraestrutura de nuvem).

## Requisitos Iniciais
- Python 3.11 ou superior.
- Certificado A1 Válido (arquivo formato `.pfx`).
- Acesso de terminal em ambiente livre de restrições pesadas de Firewall/TLS para os hosts `.fazenda.gov.br`.

## Preparando o Terreno
1. Construa o ambiente isolado:
```cmd
python -m venv venv
.\venv\Scripts\activate
```

2. Instale as bibliotecas críticas puras:
```cmd
pip install -r requirements.txt
```

## Checklist de Execução Prática

**Passo 1: Validando Sanidade ICP-Brasil e Conectividade Sefaz (01)**
Verifica se as dependências cruciais Python rodam no Sistema Operacional extraindo CNPJ e não há bloqueios de porta 443 locais. A senha agora é solicitada por input invisível.
```cmd
python prova_tecnica/01_teste_certificado.py --pfx "D:\meu_certificado.pfx"
```

**Passo 2: Investigando comportamento da Distribuição NF-e (02)**
Utiliza um NSU nulo (Zero) na fila da Fazenda. Use `producao`, informe a UF origem usando exclusivamente o código IBGE numérico de 2 dígitos (Ex: `35` para SP, `31` para MG) e forneça exatamente 14 dígitos (somente números) no `cnpj-base`.
```cmd
python prova_tecnica/02_teste_nfe.py --pfx "D:\meu_certificado.pfx" --uf-autor "35" --cnpj-base "12345678000199" --ambiente producao --salvar-exemplo-dir "./xmls_testes"
```

**Passo 3: Misto/Desfecho das limitações do CT-e Isolado (03)**
Utilize uma chave real contendo exatamente 44 dígitos, buscando contra o banco de `producao` oficial.
```cmd
python prova_tecnica/03_teste_cte.py --pfx "D:\meu_certificado.pfx" --chave-cte "35230000000000000000000000000000000000000000" --ambiente producao --salvar-exemplo-dir "./xmls_testes"
```

## Explicando a Árvore de Decisão Rumo ao MVP 1

A padronização CLI construída no HebronAutoXML vai cuspir nas suas telas a "Conclusão Técnica".
Você enxergará um destes 3 cenários finais:

1. **MVP 1 = NF-e Completa Mista (Sem Ciência de Operação)**
   - *O que acontece:* O script `02_teste_nfe.py` retorna farto **[procNFe]**.
   - *Por que comemorar:* Sua Sefaz e emissor já acoplam notas cheias e legíveis para você direto no NSU. O extrator backend será veloz.

2. **MVP 1 = NF-e com Manifestação Obrigatória do Destinatário**
   - *O que acontece:* O script `02_teste_nfe.py` esconde as notas em **[resNFe]**.
   - *Significado Tático:* Vai nos dar mais trabalho no código da próxima etapa. Teremos que embutir um motor que envie o XML de "Ciência da Operação" primeiro, retorne 200 pro WS, espere 5 minutos e só então baixe o procNFe full.

3. **MVP 1 = Foco Exclusivo NFe / CT-e = MVP 1.1**
   - *O que acontece:* O script `03_teste_cte.py` cospe *Erro de Schema Inválido SOAP Fault*.
   - *Significado Tático:* Isso significa que CT-e recusa buscas limpas por chaves neste WebService e as engloba apenas em DistNSU longas e poluídas ou demandará portais. Cortaremos fretes do MVP inicial para não atrapalhar seu software de faturamento.


_Aviso de Segurança:_ As engrenagens `.pfx` estão submeitidas em Context Managers. Transformadas em `key/pem` transientes, e ejetadas ativamente em `os.unlink()` direto do diretório `/tmp/` antes do Script parar a execução. Numa leitura post-mortem, nada subsistirá gravado.
