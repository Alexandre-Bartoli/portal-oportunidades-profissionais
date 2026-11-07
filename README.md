# Portal de Oportunidades Profissionais

Projeto experimental de pesquisa automática de oportunidades profissionais no Brasil e no exterior. O objetivo é reunir **estágios, empregos e vagas temporárias** para pessoas de todas as áreas de formação.

> **Estado atual: prova de conceito (versão 0.4).** A implementação atual pesquisa apenas **estágios** e possui conectores para quadros públicos de recrutamento Greenhouse, Lever e Ashby. As fontes ativas de exemplo não foram validadas com coleta real neste ambiente. As funções de emprego, temporários, UF, cidade e raio geográfico pertencem ao **planejamento**, ainda não ao código.

## O que já funciona no código

* Consulta a quadros de vagas Greenhouse, Lever e Ashby com identificadores de organizações configurados em `sources.json`.
* Tarefa de atualização periódica enquanto o servidor estiver executando (padrão de 6 horas).
* Identificação heurística de possíveis estágios e agrupamento aproximado por área de conhecimento.
* Armazenamento local SQLite e pesquisa textual por título, descrição e área.
* Filtro de país pelo código informado nos anúncios.
* API HTTP de leitura, interface HTML simples e diagnóstico da última coleta.
* Testes automatizados sem necessidade de conexão externa.
* Tentativas limitadas após falhas transitórias de rede, com registro de sucessos e erros por fonte.
* Vagas coletadas deixam de ser exibidas após duas consultas bem sucedidas consecutivas em que desapareceram da fonte; falhas de rede não ocasionam desativação.
* A API `/api/collection-status` informa a quantidade de fontes consultadas com sucesso e erro, vagas capturadas e registros ativos.

**Não implementado:** coleta nacional abrangente de CIEE, IEL e Nube; validação jurídica de estágios; sincronização de vagas removidas; verificação de fraude; autenticação; controle de curadoria; busca geográfica por raio; modalidades emprego e temporário; condições de produção e escalabilidade.

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
* `/api/jobs?q=...&country=BR&limit=30` : vagas classificadas como estágio.
* `/api/collection-status` : resultado da última execução.
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

## Planejamento da versão 1.0

O produto final terá escolha entre **estágio, emprego ou vagas temporárias**, seguida de **nacional, internacional ou ambos**. No Brasil, filtros de UF, município e distância máxima em quilômetros. A distância inicial será calculada em linha reta, quando existirem dados geográficos confiáveis. Veja [escopo funcional](docs/PLANEJAMENTO.md) e [roteiro de desenvolvimento](docs/ROADMAP.md).

## Segurança e responsabilidade

Este servidor liga somente em `127.0.0.1`; **não publique diretamente na Internet**. Faltam autenticação administrativa, limitação de requisições, revisão de licenciamento das fontes, testes de carga, controles de segurança e gestão de dados pessoais. Nenhum dado real de candidatos deve ser incluído no repositório. As candidaturas devem ocorrer nas fontes oficiais.

## Licenciamento

**A licença de redistribuição ainda não foi definida pelo titular.** Não foi incluído um arquivo `LICENSE` para evitar atribuir uma licença sem autorização. Recomenda-se avaliar a licença MIT para código próprio, depois de verificar a origem e as obrigações de todos os componentes.

## Estado dos testes

Execute os testes no seu ambiente. Testes locais simulam respostas de fontes externas e **não comprovam coleta real**.

## Notas da versão 0.4

A versão 0.4 melhora a **confiabilidade do processo de coleta**, mas **não confirma a existência de vagas reais coletadas** neste ambiente. As tentativas de consulta externa falharam por resolução de DNS. É indispensável executar `python3 app.py collect-auto` em um servidor com Internet, verificar os identificadores das empresas em `sources.json`, registrar pelo menos duas fontes válidas e conferir as permissões de utilização.

**Cuidado com a publicação pública:** a API de status apresenta nomes de fontes e erros abreviados, sem credenciais. Os endpoints locais continuam limitados ao computador do desenvolvedor.

## Atualização experimental 0.5: estudo Job Pindorama e AI Job Search

Foi implementado um **adaptador experimental Gupy** (`gupy.py`) com classificação de
estágio, emprego e temporárias e validação de URLs. Ele fica **desabilitado**
por padrão em `sources.json` até verificar a permissão de acesso, a estabilidade
da rota de consulta e a obtenção de vagas reais. Não é uma integração em produção.

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

A coleta agora valida a configuração antes de iniciar e diferencia três resultados:
`ok` (resposta válida com vagas), `empty` (resposta válida sem vagas) e `error`
(falha). O endpoint `/api/collection-status` inclui `audit_summary` e estados
por fonte. Falha de rede, 404 ou resposta inesperada não equivalem a zero vagas.

`source_quality.py` contém validação e diagnósticos. `listing_identity.py` fornece
IDs estáveis com provedor/quadro/ID nativo e deduplicação conservadora de URLs.
A função de deduplicação ainda **não** modifica a persistência existente.
A integração brasileira experimental continua desativada por padrão.

A consulta pública permanece prioridade. Recursos personalizados de busca,
currículos e candidaturas são planejamento futuro, com perfis privados isolados.
Veja `docs/REFERENCIAS_ADAPTACOES.md` para créditos, licença e limitações.