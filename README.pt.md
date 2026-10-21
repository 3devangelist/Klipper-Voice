# Klipper-Voice

[English](README.md) | **Português** · 📖 **[Manual de utilização, com imagens](MANUAL.pt.md)**

Põe a tua impressora Klipper a **falar**. Cada momento importante de uma impressão é dito em voz alta pela coluna do próprio anfitrião (PC, mini PC ou Raspberry Pi com saída de som), na tua língua e com as tuas frases:

> "Cama a aquecer" … "Cama quente" … "Bico a aquecer" … "Bico quente" … "10 por cento concluído" … "20 por cento concluído" … "Máquina em pausa" *(repetido de 5 em 5 minutos até voltares)* … "Impressão terminada"

- **Eventos automáticos, sem mexer nas macros:** início da impressão, cama e bico a aquecer / quentes, progresso a cada 10 %, pausa, retoma, fim, cancelamento, erro e paragens do Klipper.
- **As tuas frases:** tudo o que a impressora diz está num só ficheiro simples, o `Voice_Messages.cfg`. O **slicer** também pode dar a qualquer evento uma frase própria, só para uma impressão (`VOICE_SET`).
- **Nunca percas uma pausa:** enquanto a impressora espera por filamento ou por uma troca de cor, vai-te lembrando de N em N minutos.
- **As tuas próprias mensagens** a partir de qualquer macro ou do G-code personalizado do slicer: `SAY MSG="..."`.
- **8 línguas prontas**, escolhidas na instalação: English, Deutsch, Español, Français, Italiano, Polski, Português (Brasil), Português (Portugal). Acrescentar outra é um único ficheiro JSON.
- Vozes naturais e offline ([piper](https://github.com/OHF-Voice/piper1-gpl)), com o espeak-ng como alternativa. Só ferramentas open-source: piper, espeak-ng, sox, ALSA.
- Extra opcional para impressoras com parafusos manuais na cama e uma sonda: nivelamento da cama guiado por voz.

```
Klipper ──► Moonraker ──► klipper_voice.py (serviço systemd)
  estado da impressão,         │  vigia os eventos, escolhe a frase
  aquecimento, progresso,      ▼
  SAY/VOICE_SET         piper / espeak-ng → sox → aplay → coluna
```

O Klipper nunca toca na placa de som: o serviço ouve o Moonraker como um processo separado, com prioridade baixa e limitado a um núcleo do processador. Se a voz encravar, a impressão não é afetada.

## Requisitos

- Klipper + Moonraker (KIAUH ou semelhante), com Mainsail ou Fluidd;
- Debian, Raspberry Pi OS ou Armbian;
- uma saída de som no anfitrião (coluna interna, jack, USB ou HDMI);
- ~200 MB de disco (ambiente Python + uma voz).

Em ARM de 32 bits (armv6/armv7, por exemplo o Raspberry Pi OS de 32 bits) o piper não pode ser instalado, por isso a impressora fala com o espeak. Um sistema de 64 bits dá-te as vozes naturais.

> [!WARNING]
> **Ainda por testar — a ajuda é bem-vinda.** Até agora o Klipper-Voice só correu numa impressora: uma Ender 6 com um mini PC x86 (HP EliteDesk 800 G2 Mini), Debian 13 e Mainsail, a falar português de Portugal.
> - **Ainda não testado:** Raspberry Pi (64 bits com piper, 32 bits com espeak) e Fluidd.
> - **Traduções:** só o português de Portugal foi revisto por alguém nativo. As frases nas outras línguas foram escritas com ajuda de IA, e as respetivas vozes do piper ainda não foram ouvidas.
>
> Se o experimentares noutra máquina ou noutra língua, conta-nos como correu, ou envia correções, num [issue](https://github.com/3devangelist/Klipper-Voice/issues) ou num pull request.

## Instalação

```bash
cd ~
git clone https://github.com/3devangelist/Klipper-Voice.git
cd Klipper-Voice
./install.sh
```

O instalador **pergunta em que língua** a impressora deve falar. A língua decide que modelo de voz é descarregado para o sintetizador e que frases são escritas na tua configuração.

```
Which language should the printer speak?
   1) English                (en, voice en_US-lessac-medium)
   2) Deutsch                (de, voice de_DE-thorsten-medium)
   ...
   8) Português (Portugal)   (pt_PT, voice pt_PT-tugão-medium)
Number [1]:
```

Opções para instalar sem perguntas:

- `-l pt_PT`: escolhe a língua sem a pergunta;
- `-v en_GB-alba-medium`: outra voz do [piper-voices](https://huggingface.co/rhasspy/piper-voices);
- `-c ~/printer_data`: outra pasta printer_data;
- `-n`: sem voz natural, só espeak.

O instalador:

1. instala o `alsa-utils`, o `espeak-ng`, o `sox` e o `python3-venv`;
2. tira o som do silêncio, grava o volume e, nas placas Intel, desliga a poupança de energia que as faz estalar;
3. cria o ambiente Python `~/klipper-voice-env` com o piper;
4. descarrega a voz para `~/klipper-voice-voices/`. Se o download falhar, o serviço usa o espeak;
5. liga `~/printer_data/config/Voice` → `~/Klipper-Voice/Configuration`;
6. cria **uma só vez**, na tua língua, o `Voice_Messages.cfg` (o que a impressora diz), o `Voice_Settings.cfg` (volume, velocidade e o extra do nivelamento), o `klipper-voice.conf` (intervalos, introcall, modo noturno) e as pastas de sons em `voice_sounds/`;
7. cria e arranca o serviço `klipper-voice`, que diz a frase de arranque.

Pode ser corrido outra vez sem perigo: os teus ficheiros nunca são substituídos. Para mudar de língua, apaga o `Voice_Messages.cfg`, o `Voice_Settings.cfg` e o `klipper-voice.conf` e corre `./install.sh -l <código>`.

### Depois de instalar (uma vez)

No `printer.cfg`:

```ini
[include Voice/Voice.cfg]
[include Voice_Messages.cfg]
[include Voice_Settings.cfg]
```

Reinicia o Klipper e escreve `VOICE_TEST` na consola. A partir daí os eventos automáticos já funcionam. O [manual de utilização](MANUAL.pt.md) mostra o uso no dia a dia no Mainsail, passo a passo.

Muito alto, muito rápido? Muda no `Voice_Settings.cfg`, como qualquer outra definição do Klipper, e depois Save & Restart:

```ini
[gcode_macro _VOICE_SETTINGS]
variable_volume: 70       # 0..100
variable_speed: 1.6       # 1.0 normal, maior = mais devagar
```

Ou afina de ouvido pela consola: `VOICE_VOLUME VOLUME=70`, `VOICE_SPEED SPEED=1.6`. Cada mudança é aplicada logo e gravada no mesmo ficheiro. Cada língua começa com a sua própria velocidade.

Para atualizar pelo Mainsail/Fluidd, acrescenta ao `moonraker.conf` (a secção tem de se chamar `klipper-voice`, igual ao serviço, senão o Moonraker recusa o `managed_services`):

```ini
[update_manager klipper-voice]
type: git_repo
primary_branch: main
path: ~/Klipper-Voice
origin: https://github.com/3devangelist/Klipper-Voice.git
virtualenv: ~/klipper-voice-env
requirements: requirements.txt
managed_services: klipper-voice
```

## O que a impressora diz (`Voice_Messages.cfg`)

Todas as frases estão num só ficheiro, o `Voice_Messages.cfg`, ao lado do `printer.cfg`. Abre-o no Mainsail/Fluidd, muda qualquer frase entre as aspas e depois **Save & Restart**:

```ini
[gcode_macro _VOICE_MESSAGES]
variable_startup: "Ender 6 conectada!"
variable_complete: "sound:done | A tua peça está pronta"
variable_progress: "{p} por cento feito"
variable_start: ""
```

- Mantém as aspas. `""` deixa essa mensagem em silêncio. Uma aspa esquecida impede o Klipper de arrancar: ele mostra a linha, corrige-a e faz Save & Restart.
- `sound:done | texto` toca um som da pasta `voice_sounds/done/` e depois o texto. Usa `|` para encadear sons e frases.
- Nunca uses `;` nem `#` dentro de uma frase.
- As frases do nivelamento da cama estão no fim do mesmo ficheiro.

## Eventos automáticos

O serviço vigia a impressora através do Moonraker e fala sozinho:

| Evento | Quando | Frase por defeito (pt_PT) |
|---|---|---|
| `start` | começa uma impressão | A impressão começou |
| `bed_heating` / `bed_hot` | temperatura da cama definida / atingida | Cama a aquecer / Cama quente |
| `nozzle_heating` / `nozzle_hot` | temperatura do bico definida / atingida | Bico a aquecer / Bico quente |
| `progress` | a cada `progress_step` % (por defeito 10) | {p} por cento concluído |
| `paused` | pausa (fim de filamento, M600, PAUSE), repetida a cada `paused_repeat_minutes` (por defeito 5) | Máquina em pausa |
| `resumed` | a impressão continua | A retomar a impressão |
| `complete` / `cancelled` | fim da impressão | Impressão terminada / Impressão cancelada |
| `error` / `shutdown` | erro na impressão / Klipper parado (uma paragem a meio da impressão diz só a frase do `shutdown`) | Erro na impressão / Atenção, o Klipper parou |

Os intervalos estão em `~/printer_data/config/klipper-voice.conf` (depois de o editares, reinicia o serviço `klipper-voice`):

```ini
[events]
progress_step = 25
paused_repeat_minutes = 3
```

- Cada mensagem começa com um **introcall**, um som de atenção como nos centros comerciais (`introcall` em `[sounds]`, vazio = desligado). Não toca quando a mensagem traz um som próprio, nem quando a anterior acabou há menos de `introcall_gap` segundos (60 por defeito), por isso o nivelamento da cama e as frases seguidas não são interrompidos.
- O progresso segue o `M73` se o teu slicer o enviar; senão, a posição no ficheiro.
- O aquecimento só é anunciado quando é a sério, pelo menos `heating_min_delta` graus, por isso as pequenas mudanças de temperatura durante a impressão ficam em silêncio.

Outras opções, todas comentadas no ficheiro: modo noturno (silêncio à noite, os erros continuam a ser ditos), motor de voz (`piper`, `espeak`, ou `text` para testar sem som), placa de som e processamento do som. O volume e a velocidade estão no `Voice_Settings.cfg`.

## Os teus próprios sons (`voice_sounds/`)

Uma pasta por som, ao lado do `printer.cfg`:

| Pasta | Toca |
|---|---|
| `pause/` | quando a impressora precisa de ti: pausa (fim de filamento, troca de cor), erro na impressão, Klipper parado |
| `done/` | impressão terminada |
| `introcall/` | antes de cada mensagem (o introcall) |

Carrega qualquer ficheiro de som para uma pasta pelo Mainsail/Fluidd: qualquer nome, wav, mp3, ogg ou flac. Se puseres vários, é escolhido um ao acaso de cada vez. Uma pasta vazia não toca som e a frase é dita na mesma. O instalador põe em cada pasta um som simples por defeito.

## Frases a partir do slicer

O Klipper corre o G-code personalizado do slicer como qualquer outro G-code, por isso o slicer também pode falar.

**Dar a um evento uma frase própria para esta impressão** com `VOICE_SET`, por exemplo no *Machine start G-code*. A frase vale até a impressão acabar, e depois voltam as frases da configuração. Um `VOICE_SET` escrito na consola fora de uma impressão é descartado quando a impressão seguinte começa.

```gcode
VOICE_SET EVENT=complete MSG="O suporte do robô está pronto"
VOICE_SET EVENT=progress MSG="%p por cento do suporte"
VOICE_SET EVENT=start MSG=""
```

- Põe as linhas `VOICE_SET` no **início** do start G-code. A frase do `start` espera `start_delay` segundos (por defeito 3) para elas chegarem a tempo, e as frases de aquecimento desses segundos são ditas a seguir.
- `MSG=""` deixa esse evento em silêncio nesta impressão.
- No slicer, escreve `%p` para a percentagem, porque o `{}` é usado pelas variáveis do próprio slicer.
- Podes usar as variáveis do slicer na frase. No OrcaSlicer, por exemplo: `VOICE_SET EVENT=complete MSG="[input_filename_base] está pronto"`.

**Dizer alguma coisa num momento exato** com `SAY`, por exemplo no *Layer change G-code*:

```gcode
{if layer_num == 1}SAY MSG="Primeira camada feita"{endif}
```

**Ou trata tu das frases de aquecimento.** Põe `variable_bed_heating`, `variable_bed_hot`, `variable_nozzle_heating` e `variable_nozzle_hot` a `""` no `Voice_Messages.cfg` e, no start G-code:

```gcode
SAY MSG="Cama a aquecer"
M190 S[bed_temperature_initial_layer_single]
SAY MSG="Cama quente, bico a aquecer"
M109 S[nozzle_temperature_initial_layer]
SAY MSG="Bico quente"
```

## Comandos para as tuas macros e para o slicer

| Comando | Faz |
|---|---|
| `SAY MSG="texto"` | diz o texto |
| `PLAY_SOUND FILE=done` | toca um som de uma pasta de `voice_sounds` (ou um ficheiro: `FILE=meu.mp3`) |
| `SAY_REPEAT SEC=60 MSG="texto"` | repete até `SAY_STOP` ou até a impressão continuar |
| `SAY_STOP` | para a repetição |
| `VOICE_SET EVENT=... MSG="..."` | frase para um evento automático, nesta impressão |
| `VOICE_RESET` | volta às frases do `Voice_Messages.cfg` |
| `VOICE_VOLUME VOLUME=70` | volume de 0 a 100 para a voz e os sons. Aplicado logo, gravado no `Voice_Settings.cfg`, e é dita uma frase de exemplo. Sem `VOLUME` mostra o valor atual |
| `VOICE_SPEED SPEED=1.4` | velocidade da fala: 1.0 normal, maior = mais devagar. Aplicada logo, gravada no `Voice_Settings.cfg`, e é dita uma frase de exemplo. Sem `SPEED` mostra o valor atual |
| `VOICE_OFF` / `VOICE_ON` | desliga / liga a voz (os erros são sempre ditos) |
| `VOICE_TEST` | diz a frase de teste (`variable_test` no `Voice_Messages.cfg`) |

**Duas regras:**

- Nunca uses `;` nem `#` dentro do `MSG`: o Klipper trata-os como comentários. As aspas duplas dentro do `MSG` passam a aspas simples.
- As frases são ditas por ordem, uma de cada vez. Se se juntarem mais de 3, as mais antigas são descartadas. Muda o `queue` no conf para alterar isso.

Para ajuda a ligar a voz às tuas macros, o **[PROMPT_AI.md](PROMPT_AI.md)** tem um texto pronto a colar no teu assistente de IA.

## Acrescentar uma língua

1. Copia `languages/en.json` para `languages/<código>.json`, por exemplo `nl.json`.
2. Traduz as frases. Escolhe uma `voice` do [piper-voices](https://huggingface.co/rhasspy/piper-voices) e um código de língua do `espeak`.
3. A língua passa a aparecer na lista do instalador. Pull requests são bem-vindos.

Antes de enviares um pull request, corre os testes (não precisam de impressora):

```bash
python3 tests/test_klipper_voice.py
python3 tests/test_languages.py
```

O GitHub também os corre a cada push. O que mudou em cada versão está no [CHANGELOG](CHANGELOG.md).

## Extra opcional: nivelar a cama por voz

Para impressoras com **parafusos manuais na cama e uma sonda**. As impressoras com nivelamento automático (Z tilt, quad gantry, load cell…) ou sem sonda não precisam dele.

Para o usar, acrescenta ao `printer.cfg` (ao lado do include do `Voice_Settings.cfg` que já tens):

```ini
[include Voice/Bed_Level_Voice.cfg]
```

Depois corre-o:

```
BED_LEVEL_VOICE                 ; aquece, espera, faz home e começa
BED_LEVEL_VOICE BED=80 SOAK=5   ; outra temperatura / outra espera (minutos)
BED_LEVEL_VOICE SOAK=0          ; sem espera (testes)
BED_LEVEL_VOICE_STOP            ; interrompe
```

A sonda fica por cima de cada parafuso, sempre a medir, e vai dizendo quanto rodar: "Aperta 45 graus", "Alivia 1 volta e 30 graus" ou "Certo". Depois passa sozinha ao parafuso seguinte e acaba com uma volta de verificação. Os graus vêm do passo do parafuso: o M4 tem 0,7 mm por volta, por isso 0,1 mm ≈ 51°.

Antes de o usares, preenche o `Voice_Settings.cfg`:

- `variable_screws`: coordenadas do **bico** com a sonda por cima de cada parafuso, a convenção do `[screws_tilt_adjust]`. Bico = parafuso − offset da sonda.
- `variable_pitch`: M3 = 0.5, M4 = 0.7, M5 = 0.8.
- `variable_invert: 1` se "Aperta" fizer subir a cama.

## Resolução de problemas

| Problema | Solução |
|---|---|
| Sem som | `aplay -l` para ver a placa; `alsamixer` (F6 escolhe a placa, M tira do silêncio); `sudo alsactl store` |
| A voz não diz nada | `journalctl -u klipper-voice -f` e escreve `VOICE_TEST`; o registo mostra cada evento e cada frase |
| Erro de `RESPOND` | falta o `[respond]`; o `Voice.cfg` já o inclui, confirma o `[include Voice/Voice.cfg]` |
| Voz muito baixa / muito alta | `variable_volume` no `Voice_Settings.cfg`, ou `VOICE_VOLUME VOLUME=70` na consola; vê o volume no `alsamixer`; os `effects` do conf já normalizam para −1 dB |
| Um estalo ou ruído de vez em quando | as placas de som Intel desligam-se quando estão paradas e estalam quando acordam. O `install.sh` desliga isso (`/etc/modprobe.d/klipper-voice.conf`); corre-o outra vez nas instalações antigas |
| Voz robótica | a voz do piper falta ou não carregou: vê o registo e corre `./install.sh -v <voz>` |
| Frases antigas depois de uma mudança | `Voice_Messages.cfg`: Save & Restart (Klipper). `klipper-voice.conf`: `sudo systemctl restart klipper-voice`; o `pgrep -af klipper_voice.py` tem de mostrar um só processo |
| Som na saída errada (por exemplo HDMI) | `device = plughw:1,0` no conf (os números vêm do `aplay -l`) |

## Desinstalar

```bash
~/Klipper-Voice/uninstall.sh
```

Os teus ficheiros (`Voice_Messages.cfg`, `klipper-voice.conf`, `Voice_Settings.cfg`, `voice_sounds/`) ficam guardados. Depois tira as linhas `[include Voice/...]` do `printer.cfg`.

## Créditos e licença

Criado por Ricardo Pereira para uma Ender 6 em Vila Nova de Gaia, Portugal — feito em vibe coding com o Claude.

### Como nasceu

A minha Ender 6 corria o Klipper num Raspberry Pi e nunca esteve totalmente estável: os pacotes iam-se estragando e, num só ano, morreram-me dois cartões SD. Por isso troquei o Pi por um mini PC em segunda mão, um HP EliteDesk 800 G2 Mini (Core i3-6100T, 4 GB de RAM, SSD de 128 GB), comprado por 80 euros.

Enquanto o estava a configurar, lembrei-me de que este pequeno PC já traz placa de som e uma coluna incorporada. Sem nada para acrescentar nem ligar: porque não pôr a impressora a falar? Foi assim que nasceu o Klipper-Voice.

Organização do repositório inspirada no [KAMP](https://github.com/kyleisah/Klipper-Adaptive-Meshing-Purging).

Licença: GPL-3.0. Cada voz do piper tem a sua própria licença; vê o cartão do modelo no piper-voices.
