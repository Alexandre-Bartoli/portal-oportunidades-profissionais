# Versão 0.7: verificação de fontes externas

## Finalidade

Separar três informações que não são equivalentes:

1. A fonte responde com uma estrutura válida e possui anúncios (`raw_count`).
2. O portal consegue classificar alguns anúncios como estágio, emprego ou vaga temporária (`jobs`).
3. A utilização e republicação dos dados está autorizada pelas condições da fonte (`usage_review`).

Uma resposta JSON bem sucedida não comprova autorização jurídica de redistribuição e não confirma a disponibilidade individual de todos os links.

## Comando de verificação independente do banco

```bash
python3 app.py verify-sources --min-sources 2
```

O programa lê **somente as fontes habilitadas** em `sources.json`, consulta os conectores sem gravar vagas no SQLite e salva um relatório em `data/validacao_fontes.json`. O comando retorna código 0 somente quando o mínimo de fontes completas com vagas classificadas e registros íntegros for alcançado. Caso contrário, retorna código 2. Falhas individuais de rede não são interpretadas como inventários vazios.

Para ambientes com DNS instável ou períodos de indisponibilidade, os limites podem ser reduzidos:

```bash
PORTAL_HTTP_TIMEOUT=5 PORTAL_HTTP_ATTEMPTS=1 python3 app.py verify-sources --min-sources 2
```

O limite de espera é por solicitação, de 3 a 20 segundos. Tentativas ficam entre 1 e 3. Outras implementações de HTTP têm seus próprios limites. Não utilize essa opção para concluir que uma fonte está desativada só porque respondeu lentamente.

## Significado dos estados

| Estado | Significado | Conta para validação mínima? |
| --- | --- | --- |
| `ok` | Resposta completa, ao menos uma vaga compatível e dados estruturais íntegros | Sim |
| `no_match` | Resposta completa com anúncios, nenhum classificado pelo portal | Não |
| `empty` | Resposta completa, nenhuma vaga retornada pela fonte | Não |
| `partial` | Inventário paginado ou limitado, sem cobertura completa comprovada | Não |
| `invalid_data` | Anúncios malformados ou duplicados dentro de uma coleta | Não |
| `error` | Falha de consulta, acesso, rede ou formato | Não |

`raw_count` indica o total de anúncios recebidos do provedor. `jobs` informa quantos foram normalizados e selecionados para as categorias implementadas. `examples` armazena até dois títulos e URLs públicas para conferência manual. O relatório não inclui currículos ou dados de candidatos.

### Limitações da classificação

Uma fonte pode ter vagas de emprego e receber o status `no_match` se os anúncios não informarem um tipo de contrato reconhecido e o título não indicar estágio ou trabalho temporário. Não atribuímos automaticamente a categoria emprego a qualquer título desconhecido.

A Gupy experimental e os conectores não incluídos em `sources.json` continuam desativados. Uma varredura paginada parcial **não autoriza** inativar registros ausentes.

## Diagnóstico do ambiente de elaboração em 7 de novembro de 2026

A tentativa local de consultar as quatro fontes habilitadas terminou com **quatro erros de rede**, zero fontes com vagas comprovadas e nenhum resultado validado. A causa observada foi incapacidade de resolver ou alcançar os endereços das APIs a partir do ambiente de execução. **Não há evidência de que esses quadros estejam vazios.**

Um teste independente em ambiente com internet precisa repetir o comando e comparar os resultados com as páginas originais. Esse teste não foi concluído localmente.

## GitHub Actions

O fluxo `.github/workflows/validar-fontes.yml` executa o mesmo comando em um runner do GitHub. Ele pode ser iniciado manualmente em **Actions > Validacao externa das fontes > Run workflow** e também tenta executar uma vez ao publicar o próprio arquivo de fluxo. Publica o JSON de diagnóstico como artefato de execução, inclusive quando a verificação falhar.

O resultado do GitHub Actions é um **teste adicional**, não uma autorização de republicação nem prova de que cada URL aceita candidatura. Caso o workflow esteja desabilitado no repositório, será necessário habilitá-lo nas configurações do GitHub.

## Condições para considerar a coleta validada

1. Confirmar pelo menos duas fontes independentes com `status=ok` e oportunidades reais na execução externa.
2. Abrir uma amostra de links e conferir empresa, título, localização e situação da oportunidade.
3. Registrar a revisão das condições de coleta e redistribuição, separadamente para cada portal.
4. Repetir a consulta em outra data para verificar estabilidade, falhas de rede, atualização e encerramento.
5. Somente depois considerar a ampliação das fontes e a disponibilização pública.

## Referências oficiais de formato

* Greenhouse, Job Board API: https://docs.greenhouse.io/job-board
* Lever, API de vagas: https://github.com/lever/postings-api
* Ashby, API pública de vagas: https://developers.ashbyhq.com/docs/public-job-posting-api
* SmartRecruiters, documentação: https://developers.smartrecruiters.com/

As documentações e os formatos disponíveis não substituem a análise das condições específicas de cada provedor.

## Resultado da execução externa em ambiente GitHub

A coleta técnica de 07/11/2026 **atingiu o critério mínimo**: 3 fontes com 7 vagas classificadas entre 152 anúncios recebidos. A quarta fonte respondeu normalmente, mas suas vagas não foram classificadas. A execução pode ser consultada em [GitHub Actions](https://github.com/Alexandre-Bartoli/portal-oportunidades-profissionais/actions/runs/42408717183). Este resultado não valida direitos de republicação nem cada link de candidatura. O ambiente local permaneceu sem acesso às APIs externas.

Veja [o registro de evidência](EVIDENCIA_VALIDACAO_07.md).
