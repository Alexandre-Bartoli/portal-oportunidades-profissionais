# Versão experimental 0.8: homologação de coleta e consulta em SQLite isolado

## Objetivo

Testar, de ponta a ponta, a coleta automática de anúncios reais por fontes habilitadas, a validação dos dados, a persistência no SQLite e a consulta pelo portal local. **Não é implantação pública nem autorização de redistribuição dos dados.** O fluxo da versão 0.7 continua disponível como auditoria somente leitura.

## Segurança e isolamento

* Banco principal: `data/jobs.sqlite3`.
* Banco de homologação: `data/homologacao.sqlite3`.
* Relatório de homologação: `data/homologacao_status.json`.
* Uma execução de `stage-collect` nunca escreve no banco principal. Não é necessário excluir nem migrar o banco principal.
* Não importar registros fictícios. A rotina recusa anúncios com `demo=1`.
* O servidor `stage-serve` escuta **somente em `127.0.0.1:8767`**, não inicia coleta periódica e lê apenas o banco isolado.
* Todos os arquivos sob `data/` são ignorados pelo Git. Não publique o banco, o arquivo de relatório bruto de vagas nem documentos de candidatos no repositório.
* A homologação não faz login, não se candidata e não realiza consultas às páginas individuais de inscrição.

## Executar em computador com Internet

```bash
python3 -m unittest discover -s tests -v
python3 app.py stage-collect --min-sources 2
python3 app.py stage-status
python3 app.py stage-serve
```

Acesse `http://127.0.0.1:8767`. A API da homologação inclui `/api/jobs`, `/api/health`, `/api/staging-status` e `/api/collection-status`. O campo `mode` do `/api/health` identifica o ambiente. A página exibe dados coletados e deixa claro que se trata de um protótipo, não de um serviço público.

`stage-collect` pode devolver código `2` quando não alcançar duas fontes completas com vagas válidas. Ainda assim, as fontes que responderem corretamente são armazenadas no **banco de homologação**, e o relatório é gravado. Não confundir esse código com exclusão ou corrupção de dados. Para validar as fontes sem gravar nada, use `python3 app.py verify-sources --min-sources 2`.

O arquivo de relatório tem contagens, estados por fonte e informação sobre validação de termos. Não traz descrições das vagas nem URLs individuais para evitar distribuir dados de anúncios em artefatos públicos.

## Regras de aceitação

1. Somente fontes `enabled: true` em `sources.json` são consultadas.
2. Antes de escrever, validar lista, total original, integridade dos itens, URLs HTTPS, categoria, origem e ausência de duplicidades dentro da consulta.
3. Tratar falhas, formatos inesperados e inventários parciais como situações diferentes de uma fonte realmente vazia.
4. Em respostas completas e válidas, preservar IDs, proveniência e regra de duas ausências consecutivas para inativação.
5. Em respostas parciais, incluir anúncios válidos, mas **não inativar** vagas ausentes.
6. Repetir consultas sem multiplicar os registros, inclusive quando a mesma URL aparece em mais de uma origem.
7. Não tratar `criteria.met` como comprovação de autorização de redistribuição. Essa condição exige revisão independente da fonte.
8. Manter consulta pública desligada enquanto não houver proteção de acesso, revisão de fontes, backups e implantação adequada.

## GitHub Actions

O fluxo `.github/workflows/homologacao.yml` pode ser iniciado manualmente em Actions. Também é disparado quando o próprio arquivo do fluxo for publicado. Executa os testes e, em seguida, uma coleta em banco temporário no ambiente do GitHub. O banco SQLite **não é enviado como artefato**. O único artefato gerado é `data/homologacao_status.json`, contendo estados e contagens, sem descrições ou links das vagas. O runner é descartável: a próxima execução começa com banco vazio.

**Este fluxo não hospeda o portal e não oferece armazenamento permanente.** Para visualizar as oportunidades coletadas, execute os comandos de homologação em seu computador ou em um ambiente privado permanente que atenda os controles de acesso.

## Verificações que continuam pendentes

* Conferir individualmente uma amostra de links de inscrição, título, localidade e empresa nas fontes oficiais.
* Revisar as condições de consulta, utilização e reprodução dos anúncios de cada fonte habilitada.
* Testar consultas reais em dias diferentes, inclusive indisponibilidade dos provedores.
* Executar backup/restauração do banco antes de migrar para infraestrutura permanente.
* Planejar gestão de acesso, atualização periódica, rate limiting, proteção contra exposição de dados e implantação multiusuário.
* Implementar filtros geográficos de estado, município e distância apenas com localização confiável.

## Referências de projeto

O Career Ops, Job Pindorama e AI Job Search foram utilizados como referências de arquitetura, auditoria e rastreabilidade. Esta etapa é escrita em Python para o portal, sem copiar arquivos dos projetos externos. O código e a coleta devem respeitar os direitos e condições de cada projeto e provedor.