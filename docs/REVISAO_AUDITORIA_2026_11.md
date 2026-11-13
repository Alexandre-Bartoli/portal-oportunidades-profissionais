# Revisão da auditoria de confiabilidade

## Achados confirmados e correções

Uma falha inesperada fora do tratamento individual de fontes podia deixar uma busca em andamento indefinidamente. A busca agora registra a interrupção e pode ser consultada com resultados parciais. Após quinze minutos, seu estado passa a indicar interrupção; a operação de rede em curso não é interrompida à força. Enquanto a thread anterior estiver viva, outra busca não é iniciada. Se a chamada não retornar, reinicie o servidor para liberar o processo.

Os registros recebidos são validados quanto a estrutura, tipos, tamanho e URL antes da gravação. Um lote inválido é recusado integralmente; a falha da fonte não é confundida com resultado vazio. Isso não comprova que o conteúdo dos anúncios seja verdadeiro. As consultas SQL usam parâmetros e a interface escapa os textos exibidos.

Uma exceção inesperada na coleta periódica deixa de encerrar o agendador; o erro fica no log e uma nova tentativa ocorre no intervalo seguinte. A coleta periódica continua desativada por padrão.

## Pontos do diagnóstico que exigem contexto

O painel administrativo já exige autenticação e limita tentativas. O servidor é local e a configuração não foi projetada para exposição pública. Um proxy HTTPS isoladamente não resolve autenticação, proteção de acesso ou configuração do servidor para uso público. Definir ambiente e revisar controles antes de qualquer publicação.

Os conectores possuem prazos, tentativas limitadas, validação de respostas e distinção entre falhas e resultados parciais. Eles não garantem compatibilidade futura nem cobertura completa de cada provedor. Os testes simulados não provam funcionamento em produção.

O modo WAL não foi ativado automaticamente. A ausência de WAL não prova corrupção nem um bloqueio observado. Alterar o modo altera a operação e a gestão de arquivos auxiliares; é necessário medir contenção e avaliar backup, restauração e sistema de arquivos antes da decisão. PostgreSQL não é uma migração justificada sem medição e requisitos concretos.

## Monitoramento de homologação

Os modelos em `ops/systemd/` executam `stage-collect` com banco isolado e retornam erro quando o critério mínimo não é atingido. No servidor configurado, consulte `systemctl status portal-stage-collect.timer`, `systemctl status portal-stage-collect.service` e `journalctl -u portal-stage-collect.service`. Execute `python3 app.py stage-status` no mesmo ambiente e com o mesmo `PORTAL_STAGING_DIR` para consultar o último relatório. Verifique a data de execução, erros e fontes parciais: um timer ativo não demonstra que a coleta teve sucesso. Os arquivos são exemplos e não foram instalados nem habilitados.

Para testes de rede, use ambiente isolado, fontes revisadas e sem dados de candidatos. Uma consulta técnica não constitui autorização para coletar ou redistribuir anúncios. Registre a revisão documental antes de ampliar o acesso ou publicar dados.
