# Homologação experimental 0.9: persistência, cópias de segurança e revisão de links

## Objetivo

Preparar a homologação local da versão 0.8 para **conservar seus dados entre execuções**, criar backups consistentes, restaurar o banco quando necessário e registrar a revisão documental das fontes. O código permanece um protótipo, **não é um serviço público hospedado**. O GitHub Actions utiliza máquinas descartáveis e não constitui armazenamento permanente.

## 1. Persistência em volume privado

O caminho padrão continua `data/homologacao.sqlite3`, dentro de uma pasta ignorada pelo Git. Para operar com armazenamento durável, configure `PORTAL_STAGING_DIR` **antes** de abrir a aplicação. O valor deve ser um caminho absoluto em uma unidade persistente sob controle do operador, preferencialmente fora da árvore do projeto.

Exemplo Linux:

```bash
export PORTAL_STAGING_DIR="$HOME/portal-oportunidades-dados/homologacao"
python3 app.py stage-collect --min-sources 2
python3 app.py stage-status
python3 app.py stage-serve
```

O servidor de homologação continua disponível **somente em** `127.0.0.1:8767`. O servidor não liga o coletor automaticamente. `stage-collect` precisa ser acionado pelo operador ou por agendador do próprio computador. O diretório de dados passa a ter permissões restritas para o usuário do processo em sistemas Unix.

**Atenção:** configurar uma pasta em um runner do GitHub Actions não transforma esse armazenamento em persistente. Para não perder dados, o computador ou volume precisa sobreviver à execução e possuir política própria de cópias externas seguras.

## 2. Cópias consistentes de segurança

```bash
python3 app.py stage-backup
python3 app.py stage-backups
```

`stage-backup` utiliza a API de backup do SQLite, verifica a integridade da cópia, cria um arquivo local com nome datado e mantém os dez backups mais recentes. A coleta executada por `stage-collect` também cria backup **após uma execução com ao menos uma fonte completa contendo vagas**. Falhas de rede, sem qualquer fonte nessa condição, não geram rotação desnecessária de backups.

Os arquivos ficam em `PORTAL_STAGING_DIR/backups/` (ou `data/backups/` se não houver variável definida). Não entram no Git e não são enviados como artefatos pelo GitHub Actions.

A rotação local de dez arquivos **não substitui backups em outro dispositivo**, nem proteção contra perda do disco, comprometimento ou desastres. O transporte, a criptografia e a retenção externa devem ser definidos pelo responsável pela implantação.

## 3. Restauração manual e teste de recuperação

Pare primeiro o servidor de homologação e encerre quaisquer coletores. Consulte `stage-backups`, copie o nome exato e execute:

```bash
python3 app.py stage-restore --name homologacao-AAAAMMDDTHHMMSSffffffZ.sqlite3 --confirm
```

O comando valida formato, procedência local e integridade do backup, recusa links simbólicos e bancos com anúncios fictícios. Antes de substituir o arquivo existente, gera outra cópia de segurança. Um bloqueio entre processos impede restauração enquanto o servidor ou uma coleta estão em operação (em Windows, use somente um comando por vez).

Não aceite arquivos SQLite enviados por terceiros como backups confiáveis. O comando só restaura arquivos presentes na pasta de backup configurada. A restauração usa substituição atômica do arquivo principal e deve ocorrer com todos os processos que utilizam o banco encerrados.

## 4. Revisão documental das fontes

```bash
python3 app.py stage-review-sources
```

A documentação das fontes continua **pendente**. Uma resposta HTTP bem sucedida não concede autorização de acesso automatizado nem de redistribuição de dados. A rotina exibe o estado de cada fonte sem inventar aprovações.

Para registrar a decisão responsável por uma fonte, acrescentar à respectiva entrada em `sources.json`, após uma análise humana documentada:

```json
{
  "usage_review": "approved",
  "usage_scope": "technical_access",
  "usage_evidence_url": "https://ENDERECO-OFICIAL-DA-FONTE/termos",
  "usage_reviewed_at": "2026-11-07",
  "usage_reviewed_by": "Responsavel pela revisao"
}
```

Esse bloco é **apenas um modelo**, não deve ser copiado como se representasse revisão concluída. `technical_access` cobre exclusivamente a verificação técnica. Para o sistema declarar revisão de republicação concluída, o escopo precisa ser `republication` com documento realmente analisado e evidência verificável. O registro do operador não substitui parecer jurídico.

No momento da publicação desta versão, nenhuma fonte foi registrada como aprovada.

## 5. Auditoria restrita de links

```bash
python3 app.py stage-check-links --limit 12
```

Por padrão, a operação é **sem rede** e mostra quais anúncios poderiam ser examinados. Para consultar páginas em caráter técnico, a execução explícita exige `--network` e só envia requisições para fontes cujo registro documental autorize, ao menos, `technical_access`.

```bash
python3 app.py stage-check-links --network --limit 12
```

A operação utiliza somente `HEAD` com tempo limite, não segue redirecionamentos, não acessa domínios arbitrários, não envia currículos e **não modifica a situação de nenhuma vaga**. HTTP 200 significa somente que a URL respondeu, não que a inscrição esteja aberta. HTTP 404 ou 410 é indício a confirmar, não exclusão automática. Outros estados, como 403, 429 e falhas de rede, são tratados como inconclusivos.

A amostra é limitada a 30 vagas e distribuída por fonte. O relatório privado mostra somente identificadores abreviados, nomes das fontes e códigos de resposta. Não inclui URLs ou descrições de vagas.

## 6. Agendamento

Os arquivos em `ops/systemd/` são **modelos desativados** de serviço e temporizador para Linux. Substitua os caminhos de exemplo e analise os termos das fontes antes de instalar ou habilitar a rotina. O agendamento não é necessário para os testes e não é ativado pelo instalador, porque não existe instalador automático nesta versão.

## 7. Verificações e limites

* Execute `python3 -m unittest discover -s tests -v` para validar backup, restauração, locks, revisão e checagem de links sem rede.
* O GitHub Actions faz uma coleta temporária e executa os novos diagnósticos; ele **não armazena o banco ou os backups** como artefatos.
* O banco da etapa 0.8, se estiver na pasta padrão, não é migrado automaticamente para a pasta definida em `PORTAL_STAGING_DIR`. O operador deverá fazê-lo com cópia de segurança e revisão do conteúdo.
* Autenticação, hospedagem permanente, disponibilidade externa, backup externo, revisão das condições de uso, filtros por cidade/raio e segurança para multiusuário continuam pendentes.
* A futura busca individual de emprego utilizará dados privados segregados do catálogo público; perfis pessoais não são guardados nesta versão.