# Klipper-Voice — Manual de utilização

[English](MANUAL.md) | **Português**

Este manual mostra como usar o Klipper-Voice no dia a dia a partir do Mainsail. Para o instalar, vê o [README](README.pt.md). Tudo o que está aqui faz-se no browser; não precisas de SSH.

## Índice

1. [O que vais ouvir](#1-o-que-vais-ouvir)
2. [Testar a voz](#2-testar-a-voz)
3. [Onde está cada coisa](#3-onde-está-cada-coisa)
4. [Mudar o que a impressora diz](#4-mudar-o-que-a-impressora-diz)
5. [Volume e velocidade](#5-volume-e-velocidade)
6. [Os teus próprios sons](#6-os-teus-próprios-sons)
7. [Frases a partir do slicer e das tuas macros](#7-frases-a-partir-do-slicer-e-das-tuas-macros)
8. [Os botões das macros](#8-os-botões-das-macros)
9. [Reiniciar a voz](#9-reiniciar-a-voz)
10. [Atualizações](#10-atualizações)
11. [Nivelar a cama por voz](#11-nivelar-a-cama-por-voz)
12. [Se algo não estiver bem](#12-se-algo-não-estiver-bem)

## 1. O que vais ouvir

Depois de instalado, a impressora fala sozinha. Não tens de mudar nenhuma macro.

| Momento | Exemplo (português de Portugal) |
|---|---|
| O Klipper-Voice arranca | Impressora conectada! |
| Começa uma impressão | A impressão começou |
| A cama ou o bico aquecem e ficam quentes | Cama a aquecer … Cama quente … Bico a aquecer … Bico quente |
| A cada 10 % | 10 por cento concluído |
| Pausa (fim de filamento, troca de cor) | *som de pausa* + Máquina em pausa, repetido de 5 em 5 minutos até voltares |
| A impressão continua | A retomar a impressão |
| Impressão terminada | *som de fim* + Impressão terminada |
| Impressão cancelada | Impressão cancelada |
| Erro, ou o Klipper para | *som de pausa* + Erro na impressão / Atenção, o Klipper parou |

Antes de cada mensagem ouves um pequeno **introcall** (o "ding-dong" dos centros comerciais), para saberes que vem aí uma mensagem. Não toca quando as mensagens vêm seguidas, por exemplo durante o nivelamento da cama.

## 2. Testar a voz

Abre a **Console** e escreve:

| Comando | O que acontece |
|---|---|
| `VOICE_TEST` | a impressora diz a frase de teste |
| `VOICE_VOLUME` | mostra o volume |
| `VOICE_SPEED` | mostra a velocidade da fala |

![Consola com os comandos de voz](docs/images/console-voice-commands.png)

## 3. Onde está cada coisa

Abre **Machine**. O Klipper-Voice usa estes ficheiros e pastas, ao lado do `printer.cfg`:

![Página Machine: os ficheiros do Klipper-Voice](docs/images/machine-config-files.png)

| Ficheiro / pasta | O que tem |
|---|---|
| `Voice_Messages.cfg` | **o que a impressora diz**: todas as frases |
| `Voice_Settings.cfg` | **volume e velocidade**, e as definições do nivelamento da cama |
| `voice_sounds/` | **os sons**: uma pasta por som |
| `klipper-voice.conf` | definições técnicas (intervalos, introcall, modo noturno). Normalmente nunca lhe mexes |
| `Voice/` | as macros do próprio programa. **Não edites**: são substituídas a cada atualização |

À direita, o **Update Manager** mostra o `klipper-voice`, para o atualizares como o Klipper e o Mainsail.

## 4. Mudar o que a impressora diz

1. Em **Machine**, clica em **`Voice_Messages.cfg`**.
2. Muda o texto **entre aspas**.
3. Clica em **SAVE & RESTART** (canto superior direito).

![A editar o Voice_Messages.cfg](docs/images/editor-voice-messages.png)

Regras simples:

- **Mantém as aspas:** `variable_complete: "A tua peça está pronta"`.
- **Aspas vazias = silêncio:** `variable_start: ""` faz com que o início da impressão não seja anunciado.
- **Um som antes do texto:** `"sound:done | A tua peça está pronta"` toca um som da pasta `voice_sounds/done/` e depois diz o texto.
- **Percentagem:** em `variable_progress`, o `{p}` passa a ser o número: `"{p} por cento concluído"`.
- **Nunca uses `;` nem `#`** dentro de uma frase. O Klipper lê-os como início de um comentário e corta a frase.
- **O nome da tua impressora:** por exemplo `variable_startup: "Ender 6 conectada!"`.

As frases do nivelamento da cama estão no fim do mesmo ficheiro.

## 5. Volume e velocidade

Estão no topo do **`Voice_Settings.cfg`**:

![Volume e velocidade no Voice_Settings.cfg](docs/images/editor-voice-settings.png)

- `variable_volume`: de 0 a 100, para a voz e para todos os sons.
- `variable_speed`: 1.0 é a velocidade normal; um número maior fala mais devagar (1.5, 1.75…).

Muda o número e clica em **SAVE & RESTART**.

**Mais rápido, de ouvido, pela Console:**

```
VOICE_VOLUME VOLUME=70
VOICE_SPEED SPEED=1.6
```

A mudança é aplicada logo e a impressora diz a frase de teste, para ouvires o resultado. O valor também fica gravado no `Voice_Settings.cfg`, por isso mantém-se depois de reiniciar.

## 6. Os teus próprios sons

A pasta `voice_sounds/` tem uma pasta por som:

![As pastas dos sons](docs/images/voice-sounds-folders.png)

| Pasta | Toca |
|---|---|
| `pause/` | quando a impressora precisa de ti: pausa, fim de filamento, troca de cor, erro, Klipper parado |
| `done/` | impressão terminada |
| `introcall/` | antes de cada mensagem (o "ding-dong") |

Para trocar um som:

1. Abre a pasta, por exemplo `done`.
2. Clica no botão de **carregar ficheiro** (marcado a laranja) e escolhe o teu ficheiro.

![A carregar um som para a pasta done](docs/images/voice-sounds-upload.png)

- **Qualquer nome** e **qualquer formato comum**: mp3, wav, ogg, flac…
- **Vários ficheiros na mesma pasta?** É escolhido um ao acaso de cada vez.
- **Para voltar ao som antigo**, apaga o teu e deixa o ficheiro original.
- Uma **pasta vazia** não toca som, mas a frase é dita na mesma.
- Ficheiros MIDI (`.mid`) não funcionam. Converte-os primeiro para mp3.

## 7. Frases a partir do slicer e das tuas macros

O G-code personalizado do teu slicer, e as tuas próprias macros, também podem falar.

**Dizer alguma coisa:**

```gcode
SAY MSG="Primeira camada feita"
```

**Dar a um evento uma frase só para esta impressão**, por exemplo logo no início do *Start G-code* do slicer:

```gcode
VOICE_SET EVENT=complete MSG="O suporte do robô está pronto"
VOICE_SET EVENT=progress MSG="%p por cento do suporte"
```

- No slicer, escreve `%p` para a percentagem (o slicer usa `{}` para si próprio).
- `MSG=""` deixa esse evento em silêncio nesta impressão.
- Quando a impressão acaba, voltam as frases do `Voice_Messages.cfg`.

**Outros comandos:**

| Comando | O que faz |
|---|---|
| `PLAY_SOUND FILE=done` | toca um som de uma pasta de `voice_sounds` |
| `SAY_REPEAT SEC=60 MSG="Falta filamento"` | repete até `SAY_STOP`, ou até a impressão continuar |
| `SAY_STOP` | para a repetição |
| `VOICE_OFF` / `VOICE_ON` | desliga / liga a voz (os erros são sempre ditos) |
| `VOICE_RESET` | cancela as frases do `VOICE_SET` |

Precisas de ajuda para ligar a voz às tuas macros? O [PROMPT_AI.md](PROMPT_AI.md) tem um texto pronto a colar no teu assistente de IA.

## 8. Os botões das macros

Em **Dashboard → Macros**, cada comando tem um botão. Os que têm uma seta pedem um valor (por exemplo **VOICE VOLUME → VOLUME**).

![Os botões das macros](docs/images/macros-panel.png)

## 9. Reiniciar a voz

Clica no ícone de **energia** (canto superior direito) → **Service Control → Klipper-voice** → reiniciar (↻).

![Reiniciar o serviço Klipper-voice](docs/images/services-menu.png)

Só precisas disto depois de mexer no `klipper-voice.conf`. Para o `Voice_Messages.cfg` e o `Voice_Settings.cfg` basta o **SAVE & RESTART**.

## 10. Atualizações

Em **Machine → Update Manager**, o `klipper-voice` atualiza-se como o Klipper e o Mainsail. Os teus ficheiros (`Voice_Messages.cfg`, `Voice_Settings.cfg`, `klipper-voice.conf` e `voice_sounds/`) nunca são substituídos.

## 11. Nivelar a cama por voz

Só serve para impressoras com **parafusos manuais na cama e uma sonda**. A configuração está explicada no [README](README.pt.md#extra-opcional-nivelar-a-cama-por-voz).

1. Clica em **BED LEVEL VOICE**. A impressora aquece a cama, espera, faz o home e mede o primeiro parafuso (a referência).
2. Por cima de cada um dos outros parafusos vai-te dizendo o que fazer, por exemplo *"Aperta 45 graus"*, *"Alivia 1 volta e 30 graus"* ou *"Certo"*. Roda o parafuso enquanto ela fala.
3. Depois de dois "Certo" seguidos passa sozinha ao parafuso seguinte, e no fim volta a verificar todos.
4. **BED LEVEL VOICE STOP** interrompe a qualquer momento.

## 12. Se algo não estiver bem

| Problema | O que fazer |
|---|---|
| Não diz nada | Escreve `VOICE_TEST`. Se continuar em silêncio, reinicia a voz (secção 9) e vê o volume da coluna |
| Uma frase não mudou | Clicaste em **SAVE & RESTART**? Confirma as aspas e que não há `;` nem `#` |
| O Klipper dá erro depois de editares | Provavelmente falta uma aspa. Abre o ficheiro outra vez e corrige essa linha |
| Muito alto / muito baixo | `VOICE_VOLUME VOLUME=…` |
| Muito rápido / muito lento | `VOICE_SPEED SPEED=…` |

Há mais casos no [README](README.pt.md#resolução-de-problemas).
