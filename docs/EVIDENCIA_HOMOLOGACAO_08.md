# Evidência da homologação experimental 0.8

## Execução externa: 7 de novembro de 2026, 21h04, horário de Brasília

O fluxo **Homologacao isolada das vagas** do GitHub Actions executou a coleta,
validou os dados e gravou as vagas classificadas em um banco SQLite temporário.

* [Execução da homologação no GitHub Actions](https://github.com/Alexandre-Bartoli/portal-oportunidades-profissionais/actions/runs/42428056412)
* [Execução dos testes Python](https://github.com/Alexandre-Bartoli/portal-oportunidades-profissionais/actions/runs/42428056388)
* Commit testado: `53df901e3b4054976b316653a58ad4ba206fb4f5`.

| Fonte | Anúncios originais | Vagas classificadas e gravadas | Resultado |
| --- | ---: | ---: | --- |
| Lever / zippi | 4 | 3 | ok |
| Ashby / enter-ai | 28 | 3 | ok |
| Ashby / tako | 15 | 0 | no_match |
| Ashby / nubank | 105 | 1 | ok |
| **Total** | **152** | **7** | **3 fontes com resultados** |

O relatório do workflow registrou:

* `mode`: `external_network`.
* `records_processed`: **7**.
* `active_real_jobs_in_staging_db`: **7**.
* `source_aliases_in_staging_db`: **7**.
* `sources_with_valid_jobs`: **3**.
* Critério técnico mínimo: **cumprido** (duas fontes com anúncios elegíveis).
* **101 testes automatizados aprovados**, também confirmados pelo GitHub.

## O que esta evidência comprova

Os conectores conseguiram acessar quatro quadros públicos, identificar sete
anúncios elegíveis em três fontes e persistir sete registros no banco
SQLite de homologação usado na execução.

## O que ainda não comprova

* Não houve conferência manual individual dos sete links para garantir que
  permaneciam abertos para candidatura, que correspondiam às vagas e que
  os detalhes estavam atualizados.
* Não houve autorização formal verificada para republicar dados dessas fontes
  em portal aberto; o campo `usage_review` continua pendente quando não revisto.
* O banco da execução **é descartável**. O artefato retido contém apenas um
  relatório de estados e contagens, não um banco persistente nem as descrições.
* Não existe hospedagem pública ativa, domínio publicado ou sistema de usuários.
* Uma execução não demonstra estabilidade ao longo de dias ou semanas.

## Critério para próxima fase

Repetir a homologação em um ambiente privado com persistência e backups;
verificar manualmente a procedência e situação de uma amostra dos links;
revisar as condições de uso e preparar os filtros de localização.