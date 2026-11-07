# Evolução técnica 0.6: conectores, fontes e integridade do banco

## Objetivo e limites

O portal é público e voltado a vagas nacionais e internacionais nas áreas de
estágio, emprego e trabalho temporário. A busca individual será futura e
utilizará o mesmo catálogo central de vagas. Nenhum candidato é cadastrado
nesta versão. **Os conectores novos não foram testados com vagas reais.**

## Referências e direitos

Os módulos foram escritos em Python para o nosso projeto, inspirados na organização
por provedores e nos cuidados com identificação de anúncios do
[Career Ops](https://github.com/career-ops-hq/career-ops), licença MIT,
Copyright (c) 2026 Santiago Fernández de Valderrama.
Também foram analisados o
[Job Pindorama](https://github.com/rosanapegasgodoy/job-pindorama),
licença MIT, e o
[AI Job Search](https://github.com/MadsLorentzen/ai-job-search).
Os códigos JavaScript dos projetos externos não foram incorporados neste conjunto
de alterações. Qualquer reutilização literal futura exigirá preservar os avisos
originais de licença e direitos autorais.

A licença de software aberto não autoriza automaticamente a exploração ou a
redistribuição dos dados de todas as fontes consultadas.

## Novos módulos

* `providers_extra.py`: adaptadores experimentais SmartRecruiters e Breezy,
  requisições HTTPS sem redirecionamento, limitação de páginas e validação de
  respostas. Uma lista parcial marca `complete=False`.
* `provider_catalog.py`: lista capacidades, não credenciais nem autorização.
* `discover_sources.py`: reconhece URLs de Greenhouse, Lever, Ashby,
  SmartRecruiters e Breezy. A função `from_html()` extrai links de HTML já obtido,
  sem efetuar consultas externas. A rotina periódica procura sugestões a partir
  das URLs de vagas registradas.
* `core.py`: tabela `job_aliases` preserva a proveniência por conector,
  empresa e identificador nativo da oportunidade. A URL canônica permite juntar
  novos anúncios equivalentes sem alterar o ID do registro original.

## Segurança e privacidade

* Fontes descobertas ficam desabilitadas até uma revisão explícita.
* URLs com domínios semelhantes aos de provedores são rejeitadas.
* Falhas de conexão e inventários parciais não justificam o encerramento de vagas.
* O banco antigo é preservado. Migrar não remove anúncios nem reescreve os IDs.
* Anúncios duplicados que já existiam antes da migração são apenas identificados
  no relatório `audit-duplicates`, pois fundi-los sem auditoria pode causar
  perda de histórico e erros de classificação.
* A implementação não deve ser exposta diretamente à Internet. Ainda faltam
  autenticação, autorização, limite de requisições, backups testados e auditoria
  de licenciamento dos dados.

## Comandos

```bash
python3 -m unittest discover -s tests -v
python3 app.py init
python3 app.py discover-sources
python3 app.py audit-duplicates
python3 app.py collect-auto
python3 app.py serve
```

A rota `/api/providers` informa os conectores técnicos do sistema.
A rota `/api/collection-status` expõe o estado das consultas, incluindo a
situação `partial`, que significa resposta incompleta para fins de inativação.
O arquivo `data/fontes_sugeridas.json` contém apenas candidatos à configuração;
nunca é interpretado como aprovação automática de novas fontes.

## Critérios para passar à etapa seguinte

1. Confirmar formalmente as condições de consulta e de utilização de dados.
2. Validar o formato real dos anúncios e os limites de paginação.
3. Testar a coleta em fontes independentes, com resultados rastreáveis.
4. Verificar se a deduplicação não confunde vagas semelhantes de uma empresa.
5. Testar restauração de cópia de segurança antes de publicar o sistema.