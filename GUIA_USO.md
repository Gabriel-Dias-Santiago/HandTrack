# Gesture Music Studio - Guia Completo

## 1) Instalacao

Crie/ative seu ambiente e instale:

```bash
pip install opencv-python mediapipe numpy pygame
```

Execute:

```bash
python cp2.py
```

Observacao: o audio usa `pygame.midi`. Para timbres reais, instale um sintetizador MIDI no sistema (ex.: Microsoft GS Wavetable no Windows, ou synth externo).

## 2) Como Trocar Entre Modos

Gesto por zona (mais confiavel):

- Coloque a mao esquerda no TOPO da tela e mantenha estavel ~0.55s:
- 1 dedo: `MELODY`
- 2 dedos: `PERCUSSION`
- 3 dedos: `DJ`

Atalho de teclado (backup):

- `1`: Melody
- `2`: Percussion
- `3`: DJ

## 3) Modo Melodia

### Como tocar

- Mao direita:
- Eixo Y (altura): define a nota da escala.
- Eixo X: define a oitava.
- Fazer PINCA (polegar + indicador): `note on` (toca).
- Soltar a pinca: `note off` (para).

### Como sustentar

- Mantendo a mao fechada, a nota continua.
- Movendo a mao fechada na horizontal/vertical, a nota muda em tempo real.

### Controles da mao esquerda

- Punho fechado (borda de gesto): inicia/para gravacao de loop.
- Movimento circular: liga/desliga reproducão do loop.
- Troca de instrumento por zona:
- Leve a mao esquerda para a BASE da tela (faixa inferior), com mao aberta e estavel.
- Mova horizontalmente para selecionar uma das 6 faixas.
- Segure ~0.45s para confirmar troca.

## 4) Modo Percussao

### Pads na tela

- Superior esquerdo: `kick`
- Superior direito: `snare`
- Inferior esquerdo: `hi-hat`
- Inferior direito: `clap`

### Como disparar

- Mao direita: faca um tap rapido para baixo (impacto vertical) dentro da regiao desejada.

### Controles esquerda

- Punho fechado: inicia/para gravacao.
- Circular: liga/desliga loop.
- Instrumento: usar zona inferior (igual ao modo melodia).

## 5) Loop Station

### Gravacao

- Feche a mao esquerda uma vez para iniciar.
- Feche novamente para finalizar a camada.

### Reproducao e layering

- Movimento circular da mao esquerda ativa/desativa loop.
- Cada nova gravacao vira uma nova camada, sincronizada por BPM.
- Quantizacao simples ativa (grade de 1/4 de batida).

### Limpar

- Tecla `C`: limpa todas as camadas.

## 6) DJ Mode (Obrigatorio)

## Como usar DJ Mode

Entre em `DJ` com duas maos abertas (ciclo de modos).

### Mao direita - controles continuos

- Filtro (LP/HP): movimento vertical.
- Mao baixa -> tendencia low-pass.
- Mao alta -> tendencia high-pass.
- Volume: movimento horizontal.
- Esquerda = baixo volume, direita = alto volume.
- Reverb/Delay: profundidade (distancia da camera).
- Mais longe = mais ambiencia.

### Mao esquerda - triggers

- Drop:
- Punho fechado curto.
- Resultado: pequeno corte + retorno com impacto.

- Build-up:
- 1 dedo levantado e estavel por ~0.45s (toggle).
- Resultado: sobe BPM gradualmente e ativa snare roll.

- Kill FX:
- Mao aberta e parada por 1 segundo.
- Resultado: remove efeitos (som limpo).

- Loop Remix / Stutter:
- 2 dedos levantados e estaveis por ~0.45s alterna stutter on/off.

## Dicas de performance DJ

- Build-up cria tensao: use antes de transicao forte.
- Drop funciona melhor no fim do build-up.
- Stutter em trechos curtos evita poluicao.
- Combine loops gravados + DJ para performance ao vivo.

## 7) HUD / Interface na tela

A interface mostra:

- Modo atual
- Instrumento atual
- Nota atual (quando aplicavel)
- Status do looper (REC/IDLE, loop on/off, camadas)
- Pads de percussao (no modo percussao)
- Painel DJ (filtro, volume, reverb, build-up, BPM, flash de drop)

## 8) Atalhos de teclado

- `Q` ou `ESC`: sair
- `C`: limpar loops
- `+` / `-`: ajustar BPM
- `1`, `2`, `3`: Melody / Percussion / DJ
- `I`: proximo instrumento
- `O`: instrumento anterior
