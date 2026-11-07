# Evidência de verificação técnica das fontes

## Evidência externa em 7 de novembro de 2026

Uma execução do GitHub Actions em ambiente com acesso à internet retornou quatro fontes com respostas válidas, das quais três apresentaram vagas compatíveis: 152 anúncios originais e 7 vagas classificadas. A fonte Ashby/Tako retornou 15 anúncios sem correspondência nas categorias reconhecidas.

| Fonte | Anúncios originais | Vagas classificadas | Estado |
| --- | ---: | ---: | --- |
| Lever/Zippi | 4 | 3 | ok |
| Ashby/Enter AI | 28 | 3 | ok |
| Ashby/Tako | 15 | 0 | no_match |
| Ashby/Nubank | 105 | 1 | ok |

* [Execução da auditoria de fontes](https://github.com/Alexandre-Bartoli/portal-oportunidades-profissionais/actions/runs/42408717183)
* [Execução dos 86 testes automatizados](https://github.com/Alexandre-Bartoli/portal-oportunidades-profissionais/actions/runs/42408717168)

O critério técnico mínimo de duas fontes com resultados foi cumprido no GitHub Actions. A revisão de autorização de consulta e republicação permanece pendente. A verificação individual de links de candidatura e a repetição periódica dos testes também permanecem pendentes. A auditoria é somente leitura: **não inseriu vagas na base do portal**.
