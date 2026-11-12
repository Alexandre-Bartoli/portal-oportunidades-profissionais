# Portal de Oportunidades Profissionais

Projeto experimental de pesquisa automática de oportunidades profissionais no Brasil e no exterior. O objetivo é reunir **estágios, empregos e vagas temporárias** para pessoas de todas as áreas de formação.

> **Estado atual: prova de conceito (versão experimental 0.9).** A Gupy e duas empresas na InHire estão habilitadas experimentalmente, e a revisão de uso continua pendente. A coleta integrada foi verificada em homologação isolada, sem manter um serviço público disponível. A pesquisa geográfica utiliza aproximação entre sedes municipais e possui cobertura parcial.

## O que já funciona no código

* Consulta a quadros de vagas Greenhouse, Lever e Ashby, além de Gupy e InHire experimentais, configurados em `sources.json`. As demais fontes experimentais permanecem desabilitadas.
* Tarefa de atualização periódica enquanto o servidor estiver executando (padrão de 6 horas).
* Identificação heurística de possíveis estágios e agrupamento aproximado por área de conhecimento.
* Armazenamento local SQLite e pesquisa textual por título, descrição e área.
* Filtro de país pelo código informado nos anúncios.
* API HTTP de leitura, interface HTML simples e diagnóstico da última coleta.
* Testes automatizados sem necessidade de conexão externa.
* Tentativas limitadas após falhas transitórias de rede, com registro de sucessos e erros por fonte.
* Vagas coletadas deixam de ser exibidas após duas consultas bem sucedidas consecutivas em que desapareceram da fonte; falhas de rede não ocasionam desativação.
* A API `/api/collection-status` informa a quantidade de fontes consultadas com sucesso e erro, vagas capturadas e registros ativos.

**Não implementado:** coleta nacional abrangente de CIEE, IEL e Nube; validação jurídica de estágios; verificação definitiva de fraude; autenticação apropriada para produção; controle de curadoria; funcionamento em produção, escalabilidade e pesquisa personalizada de candidatos. A classificação de emprego e temporário é conservadora, não garante cobertura completa.

## Requisitos

* Python 3.10 ou superior.
* Não requer bibliotecas externas para executar a prova de conceito.
* Internet para buscar vagas reais nas fontes habilitadas.

## Executar localmente

```bash
python3 -m unittest discover -s tests -v
python3 app.py init
python3 app.py serve
```

Acesse `http://127.0.0.1:8766`.

A tarefa periódica começa ao iniciar o servidor. Para uma consulta imediata separada:

```bash
python3 app.py collect-auto
```

**Atenção:** `sources.json` inclui organizações de exemplo habilitadas. Isso não assegura que seus identificadores continuem válidos, que publiquem estágios ou que o uso de dados seja autorizado para republicação. Revise as condições de cada fonte antes de usar. É normal receber zero vagas.

Para testar sem internet com quatro **anúncios fictícios**, execute `python3 app.py demo`. Esses registros são identificados como demonstração e não devem ser apresentados como oportunidades reais. Exclua `data/jobs.sqlite3` para limpar o banco.

## Endpoints

* `/` : interface HTML.
* `/api/health` : status HTTP.
* `/vaga?id=...` : detalhes de uma oportunidade ativa; dados de demonstração permanecem identificados e são excluídos da homologação.
* `/api/jobs?q=...&country=BR&kind=internship&limit=30` : pesquisa por categoria, incluindo `employment`, `temporary` e `all`.
  A resposta informa `link_permitido`; URLs de domínios não reconhecidos para o provedor são retornadas como `null` e não são exibidas como links de candidatura.
  Também aceita `region=brazil` ou `international`, `mode=remote`, `hybrid`, `onsite` ou `unknown`, `area` com nome de área reconhecida e `offset` entre 0 e 10000. Os filtros são combinados. País desconhecido fica fora dos filtros de região; os dados ainda dependem da qualidade da fonte.
* A interface local oferece navegação por páginas de até 30 resultados. O instante mostrado nos detalhes é o último registro de coleta da vaga, não uma confirmação de que a candidatura ainda está aberta.
* `/admin` e `/api/admin` : painel e indicadores administrativos locais, protegidos por credenciais. Veja [painel administrativo](docs/PAINEL_ADMINISTRATIVO.md).
* `/api/collection-status` : resultado protegido da última execução, incluindo fontes parciais.
* `/api/providers` : catálogo técnico dos conectores.
* `/api/portals` : catálogo de referência de portais brasileiros; **não** significa integração ativa.

## Estrutura

```text
app.py             Servidor e comandos
core.py            Conectores, normalização, armazenamento e busca
automatico.py      Coleta periódica e diagnóstico
brasil.py          Catálogo e suporte legado de importação
feeds_brasil.py    Adaptadores configuráveis de parceiros
sources.json       Fontes empresariais da coleta automática
feeds_brasil.json  Modelos de integração brasileira, desativados
tests/             Testes unitários
docs/              Escopo e decisões técnicas
```

Os módulos legados de importação foram preservados do protótipo, mas **a estratégia da primeira versão planejada é pesquisa automática**, sem importar vagas manualmente. Eles não constituem integração ativa com portais brasileiros.

Para novas coletas, o país não é mais deduzido de nomes de cidades no campo de localização. O conector experimental Gupy mantém o país desconhecido quando ele não é informado explicitamente nos detalhes. Bancos anteriores podem conter países inferidos pela versão antiga, sem marca de proveniência; devem ser revisados antes de qualquer publicação, sem apagá-los automaticamente. A [pesquisa geográfica](docs/PESQUISA_GEOGRAFICA.md) usa coordenadas de sedes municipais do IBGE e exclui vagas que não puderem ser localizadas de forma conservadora.

Os conectores experimentais SmartRecruiters e Breezy rejeitam alguns registros malformados; links Breezy fora do domínio esperado tornam o inventário parcial e não devem provocar desativação de vagas ausentes. Essas verificações não substituem testes de conexão real nem revisão de condições de uso.

As consultas JSON centrais aceitam somente os domínios explícitos de Greenhouse, Lever, Ashby, Gupy e outros provedores explicitamente autorizados no código, em HTTPS, sem credenciais ou portas não autorizadas. Redirecionamentos são recusados. Mudanças de domínio dos provedores podem interromper a coleta e exigem revisão; isso não substitui uma auditoria completa de segurança de rede.

## Planejamento da versão 1.0

O produto final terá escolha entre **estágio, emprego ou vagas temporárias**, seguida de **nacional, internacional ou ambos**. No Brasil, filtros de UF, município e distância máxima em quilômetros. A distância inicial será calculada em linha reta, quando existirem dados geográficos confiáveis. Veja [escopo funcional](docs/PLANEJAMENTO.md) e [roteiro de desenvolvimento](docs/ROADMAP.md).

Os adaptadores experimentais Gupy, Sólides, Workable e Remotive, os limites de consulta, as condições de uso ainda pendentes e a revisão não destrutiva de duplicatas estão descritos em [avaliação de fontes](docs/AVALIACAO_FONTES_2026_11.md). Fontes adicionais dependem de configuração explícita. A migração aditiva SQLite chega à versão 4; faça backup antes de atualizar.

Adaptações do Radar de Vagas: leitura limitada de detalhes Gupy e conector experimental InHire por empresa. As páginas da dti digital e da Movecta estão configuradas para consulta experimental, com revisão de uso pendente. A InHire consulta até 50 detalhes por empresa em cada coleta e informa cobertura parcial. O país é reconhecido como Brasil apenas quando a localização termina com o código BR. As condições e limites constam na avaliação de fontes; o projeto de referência e sua licença MIT estão creditados nela.

A Gupy consulta até cinco páginas de 25 anúncios por categoria e prioriza até três detalhes ainda não enriquecidos por coleta. A cobertura é parcial. Os filtros geográficos aceitam siglas ou nomes completos de estados com país confirmado como Brasil; nomes de cidades sozinhos não definem o país.

Há também consultas experimentais específicas para Minas Gerais nas três categorias. Cada consulta estadual busca até 25 anúncios por coleta e tenta obter até dez detalhes, priorizando os ainda não enriquecidos. O filtro estadual só mostra vagas cuja localização e país possam ser confirmados. A configuração aceita outras UFs, mas inicialmente apenas Minas Gerais está ativada para essa consulta adicional.

O filtro de data de publicação pode mostrar vagas dos últimos 7, 14, 30 ou 90 dias. Anúncios sem data de publicação continuam aparecendo, pois não é possível determinar sua idade. As buscas por UF e o tratamento de data foram adaptados das práticas do Job Pindorama, cuja licença está em `docs/licencas_referencias/`.

A busca internacional inclui quadros públicos das empresas Cohere, Wealthsimple e Kaluza. Países informados por nome no campo de endereço são convertidos quando reconhecidos; regiões e países não reconhecidos permanecem sem classificação. Vagas remotas podem exigir residência ou autorização de trabalho no país indicado; verifique as condições no anúncio original.

Na Gupy, anúncios repetidos e anúncios sem URL válida são contabilizados no diagnóstico e não impedem a importação dos demais. URLs fora dos domínios aceitos continuam excluídas. A resposta permanece parcial e não provoca desativação de vagas ausentes.

## Segurança e responsabilidade

Este servidor liga somente em `127.0.0.1`; **não publique diretamente na Internet**. O painel tem autenticação básica para uso local, mas faltam HTTPS, controles de autenticação adequados à produção, revisão de licenciamento das fontes, testes de carga e gestão de dados pessoais. Nenhum dado real de candidatos deve ser incluído no repositório. As candidaturas devem ocorrer nas fontes oficiais.

## Licenciamento

O código próprio do projeto é disponibilizado sob a [licença MIT](LICENSE). Componentes de terceiros mantêm seus avisos de autoria e licença em [licenças das referências](docs/licencas_referencias/). A licença do software não concede direitos sobre anúncios ou dados obtidos de outras plataformas; suas condições de uso devem ser verificadas separadamente.

## Estado dos testes

Execute os testes no seu ambiente. Testes locais simulam respostas de fontes externas e **não comprovam coleta real**.

## Notas da versão 0.4

A versão 0.4 melhora a **confiabilidade do processo de coleta**, mas **não confirma a existência de vagas reais coletadas** neste ambiente. As tentativas de consulta externa falharam por resolução de DNS. É indispensável executar `python3 app.py collect-auto` em um servidor com Internet, verificar os identificadores das empresas em `sources.json`, registrar pelo menos duas fontes válidas e conferir as permissões de utilização.

**Cuidado com a publicação pública:** a API de status apresenta nomes de fontes e erros abreviados, sem credenciais. Os endpoints locais continuam limitados ao computador do desenvolvedor.

## Atualização experimental 0.5: estudo Job Pindorama e AI Job Search

Foi implementado um **adaptador experimental Gupy** (`gupy.py`) com classificação de
estágio, emprego e temporárias e validação de URLs. Ele está habilitado em
`sources.json` por opção do responsável, com condições de uso pendentes. Não é
uma integração em produção.

A API `/api/jobs` e a interface HTML agora aceitam `kind=internship`,
`kind=employment`, `kind=temporary` ou `kind=all`. Os anúncios de outras
plataformas continuam dependendo de classificação conservadora; a ausência de
um tipo explícito não prova tratar-se de emprego.

O módulo `signals.py` retorna alertas explicáveis sobre inconsistência da
modalidade de trabalho, seleção interna e solicitação de pagamento. Alertas
não constituem comprovação de fraude. A API inclui um campo `signals` em cada
resultado e não executa comandos nem segue instruções contidas em anúncios.

Leia [a avaliação técnica e os créditos](docs/REFERENCIAS_JOB_SEARCH.md).
As ideias foram inspiradas no Job Pindorama e no AI Job Search, ambos MIT;
não foi copiado código das ferramentas de linha de comando.

## Auditoria de conectores e identidade dos anúncios (atualização incremental)

A coleta agora valida a configuração antes de iniciar e diferencia resultados como:
`ok` (resposta válida com vagas), `empty` (resposta válida sem vagas), `error`
(falha) e `partial` (inventário incompleto, sem inativar registros ausentes). O endpoint `/api/collection-status` inclui `audit_summary` e estados
por fonte. Falha de rede, 404 ou resposta inesperada não equivalem a zero vagas.

`source_quality.py` contém validação e diagnósticos. `listing_identity.py` fornece
IDs estáveis com provedor/quadro/ID nativo e deduplicação conservadora de URLs.
A deduplicação inicialmente era somente um módulo auxiliar; a versão 0.6 a integra à persistência, preservando os IDs já gravados.
A integração brasileira Gupy está ativada experimentalmente; as demais fontes novas permanecem desativadas.

A consulta pública permanece prioridade. Recursos personalizados de busca,
currículos e candidaturas são planejamento futuro, com perfis privados isolados.
Veja `docs/REFERENCIAS_ADAPTACOES.md` para créditos, licença e limitações.

## Evolução experimental 0.6: catálogo, descoberta e deduplicação persistente

* **Novos provedores:** `smartrecruiters` e `breezy` implementados em Python, ainda
  sem habilitação em `sources.json` e **sem teste real de coleta**. Os conectores
  aceitam somente identificadores seguros e respostas em formato esperado.
* **Catálogo técnico:** `provider_catalog.py` e `/api/providers` mostram os seis
  conectores implementados. Presença no catálogo não equivale a acesso autorizado.
* **Descoberta passiva:** `discover_sources.py` extrai candidatos de endereços
  de vagas já coletadas, reconhecendo URLs de ATS conhecidos. Após cada coleta,
  `data/fontes_sugeridas.json` registra apenas *sugestões desativadas*. Nenhum
  conector é incluído automaticamente em `sources.json`; é necessária validação.
  O comando `python3 app.py discover-sources` mostra as sugestões sem rede.
  A função `from_html()` pode estudar links de uma página HTML fornecida pelo
  responsável, sem abrir links ou acessar a rede.
* **Deduplicação persistente:** `core.save()` une novos anúncios pela URL canônica
  HTTPS, preservando o ID original, e a tabela `job_aliases` armazena a origem
  de cada anúncio. Uma fonte que encerra a vaga não a desativa enquanto outra
  origem permanecer ativa. Títulos semelhantes nunca são prova de duplicidade.
* **Migração aditiva:** o banco SQLite preexistente é atualizado sem excluir
  registros nem alterar os IDs antigos. Grupos de duplicatas antigas **não são
  fundidos automaticamente**; use `python3 app.py audit-duplicates` para auditar.
* **Paginação incompleta:** um provedor que retorna somente parte do catálogo
  não causa desativação de vagas ausentes, e aparece como `partial` na auditoria.

**Limitações:** nenhum conector novo foi validado com anúncios reais. A descoberta
é passiva e não vasculha a Web em busca de novas empresas. A automação geral
continua dependendo do servidor local em execução. O software não possui os
controles necessários para uma implantação pública. Candidaturas individualizadas
são uma etapa futura. Consulte `docs/EVOLUCAO_06.md`.

## Versão experimental 0.7: auditoria externa independente

O comando `python3 app.py verify-sources --min-sources 2` consulta as fontes
habilitadas sem modificar ou expirar vagas no banco. Ele registra tanto a
quantidade de anúncios retornados pelo provedor (`raw_count`) quanto a
quantidade de vagas reconhecidas pelo portal (`jobs`). Distingue fontes vazias,
fontes sem vagas compatíveis, consultas incompletas, respostas malformadas e
erros de conexão.

O JSON é salvo em `data/validacao_fontes.json` (arquivo local ignorado pelo Git).
O comando retorna código 2 caso não encontre o mínimo de fontes completas com
resultados válidos. Existe também um workflow manual do GitHub Actions para
repetir essa verificação em um ambiente independente.

A tentativa local de 7 de novembro de 2026 terminou com **quatro falhas de rede**
e zero fontes confirmadas. Esse resultado não indica ausência de vagas.

Consulte [o procedimento e os critérios de validação](docs/VALIDACAO_07.md).


## Homologação isolada da versão experimental 0.8

A nova versão permite **coletar anúncios para um banco separado** e consultar os
resultados pela API e página local, sem modificar o banco principal:

```bash
python3 -m unittest discover -s tests -v
python3 app.py stage-collect --min-sources 2
python3 app.py stage-status
python3 app.py stage-serve
```

Abra `http://127.0.0.1:8767` após a coleta. `stage-serve` não inicia o
agendador. O ambiente de homologação utiliza `data/homologacao.sqlite3`, enquanto
o banco principal continua em `data/jobs.sqlite3`. Ambos são ignorados pelo Git.
Um relatório sanitizado em `data/homologacao_status.json` indica as fontes
consultadas, quantos anúncios foram classificados e quantos continuam ativos.

O workflow `.github/workflows/homologacao.yml` usa um banco temporário no runner
do GitHub, executa os testes e tenta uma coleta real, guardando **somente o
relatório**, nunca o banco com descrições dos anúncios. Isso não disponibiliza o
portal pela internet nem garante armazenamento permanente. Não significa que
um anúncio individual esteja aberto para candidatura ou que tenhamos autorização
para redistribuí-lo publicamente.

Leia [o procedimento de homologação e limites](docs/HOMOLOGACAO_08.md).


## Evidência da homologação real (07/11/2026)

O GitHub Actions concluiu a coleta em banco temporário: **152 anúncios recebidos,
7 vagas classificadas e gravadas, 3 fontes com resultados**. Os **101 testes
Python** também passaram. Isso comprova a etapa técnica de persistência em
homologação, mas **não** constitui autorização de republicação, verificação
manual dos links ou implantação pública. Consulte
[os dados, limites e execuções](docs/EVIDENCIA_HOMOLOGACAO_08.md).

## Evolução experimental 0.9: homologação com dados persistentes e recuperação

* `PORTAL_STAGING_DIR` permite usar um volume local persistente absoluto, isolado do banco principal e com permissões restritas.
* `python3 app.py stage-backup` cria snapshot consistente e validado, com rotação local de dez arquivos.
* `stage-collect` cria backup automático quando pelo menos uma fonte completa retorna vagas.
* `stage-backups` lista cópias. `stage-restore --name ARQUIVO --confirm` valida e restaura com cópia anterior e bloqueio contra servidor em execução.
* `stage-review-sources` registra pendências e evidências documentais sem supor autorização.
* `stage-check-links` apresenta amostra sem rede por padrão; `--network` só consulta domínios conhecidos de fontes com revisão técnica registrada. Resposta HTTP não comprova candidatura aberta nem modifica vagas.
* Os modelos de agendamento em `ops/systemd/` não são ativados automaticamente.

**Não há hospedagem permanente instalada por este código:** o operador precisa providenciar a unidade persistente, a revisão das fontes e o ambiente protegido. A validação de links reais permanece pendente enquanto as fontes estiverem sem documentação aprovada.

Leia [o procedimento da versão 0.9](docs/HOMOLOGACAO_09.md).
