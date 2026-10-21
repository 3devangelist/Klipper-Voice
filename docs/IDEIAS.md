# Ideias e trabalho pendente

Notas para continuar noutro dia. Não fazem parte do Klipper-Voice publicado.

## 1. Mapa de fita de alumínio para endireitar a cama

**Ideia:** a cama da Ender 6 está torta. Um script lê a malha (bed mesh) que o Klipper já mediu e diz **onde** colar fita de alumínio por baixo do vidro e **quantas camadas** em cada sítio, num mapa visual (tipo mapa 3D / mapa de calor com o número de camadas por zona).

### Dados que já existem na Ender6 (21/10/2026)

- Malhas guardadas no `printer.cfg`: perfis **`default`** e **`full`** (nenhuma carregada por defeito).
- `[bed_mesh]`: `probe_count: 10,10`, `mesh_min: 6,6`, `mesh_max: 239,239`, `algorithm: bicubic`.
- Sonda **indutiva**: `x_offset: -28`, `y_offset: 0.5`, `z_offset: 2.325`.
- Ler a malha pela API do Moonraker:
  `http://192.168.1.89:7125/printer/objects/query?bed_mesh` → `bed_mesh.profiles.full.points` (matriz 10×10 de alturas em mm) e `mesh_params` (min/max X e Y).

### Método proposto

1. Ler a malha `full` (ou medir de novo: `BED_MESH_CALIBRATE PROFILE=full`, com a cama quente).
2. **Tirar a inclinação** (ajustar um plano aos pontos): a inclinação resolve-se com os parafusos (BED_LEVEL_VOICE), a fita só serve para as **covas** que sobram.
3. Diferença de cada ponto para o ponto mais alto (ou para o percentil 90, para ignorar picos isolados).
4. Camadas por zona = diferença ÷ espessura da fita, arredondado. Medir a espessura real da fita com um paquímetro (fita de alumínio de canalização costuma ter 0,05 a 0,08 mm com cola).
5. Mapa: grelha 10×10 sobre a cama (235×235 mm), cada célula com a cor da profundidade e o número de camadas; camadas em degrau (as maiores por baixo, mais pequenas, as seguintes por cima a cobrir mais área), para não fazer degraus bruscos.
6. Saída: uma página HTML com o mapa e as medidas em mm de cada zona, para imprimir e colar por cima do vidro como guia.

### ⚠️ Cuidado: sonda indutiva

A sonda indutiva **não vê o vidro**: mede a placa de alumínio por baixo. Se a fita for posta entre a placa e o vidro:

- o vidro fica direito, mas a sonda continua a "ver" a placa torta;
- a malha passa a compensar uma curvatura que o vidro já não tem → **dupla correção**.

Por isso, depois de pôr a fita, é preciso decidir: **desligar a malha** (ou usar uma malha plana) e voltar a afinar o Z offset, **ou** medir o vidro de outra forma (folha de papel / apalpa-folgas, ou um sensor que toque no vidro). Pensar nisto antes de colar fita.

### Ainda por decidir

- Onde fica o script: dentro do Klipper-Voice (não tem a ver com voz) ou num repositório próprio.
- Se corre no PC (lê a API e abre o HTML) ou na impressora (macro que gera o ficheiro).

## 2. Klipper-Voice: o que ficou por fazer

- [ ] Capturas novas da consola e do painel de Macros para o manual (as atuais mostram os comandos antigos `VOICE_TEST`, `VOICE_VOLUME`…).
- [ ] Publicar a **Release v1.9.0** no GitHub (comando `VOICE`, `SAY … WAIT=1`, voz mais clara, macros de exemplo, nivelamento à espera da voz).
- [ ] Confirmar as posições dos parafusos 2, 3 e 4 no `Voice_Settings.cfg` (vinham do antigo `NIVELAR_VOZ`, marcadas como "por medir").
- [ ] Testar num Raspberry Pi e no Fluidd; pedir revisão das traduções (de, es, fr, it, pl, pt_BR).
