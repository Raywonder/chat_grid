import { GRID_SIZE, isItemQuiet, type GameState, type PeerState, type WorldItem } from '../state/gameState';

export class CanvasRenderer {
  private readonly ctx: CanvasRenderingContext2D;
  private squarePixelSize: number;
  private gridSize: number;

  constructor(private readonly canvas: HTMLCanvasElement) {
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      throw new Error('Unable to create 2D context');
    }
    this.ctx = ctx;
    this.gridSize = GRID_SIZE;
    this.squarePixelSize = canvas.width / this.gridSize;
  }

  setGridSize(gridSize: number): void {
    if (!Number.isInteger(gridSize) || gridSize <= 0) return;
    this.gridSize = gridSize;
    this.squarePixelSize = this.canvas.width / this.gridSize;
  }

  draw(state: GameState): void {
    const { ctx } = this;
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    ctx.strokeStyle = '#374151';
    for (let i = 0; i <= this.gridSize; i += 1) {
      ctx.beginPath();
      ctx.moveTo(i * this.squarePixelSize, 0);
      ctx.lineTo(i * this.squarePixelSize, this.canvas.height);
      ctx.moveTo(0, i * this.squarePixelSize);
      ctx.lineTo(this.canvas.width, i * this.squarePixelSize);
      ctx.stroke();
    }

    for (const peer of state.peers.values()) {
      this.drawObject(peer, '#f87171', peer.nickname);
    }
    for (const item of state.items.values()) {
      if (item.carrierId) continue;
      if (isItemQuiet(item)) continue;
      this.drawItem(item);
    }
    this.drawObject(state.player, '#34d399', state.player.nickname);

    if (state.mode === 'nickname' || state.mode === 'chat' || state.mode === 'itemPropertyEdit') {
      const label =
        state.mode === 'nickname'
          ? 'New Nickname'
          : state.mode === 'chat'
            ? state.directMessageTargetName
              ? `DM to ${state.directMessageTargetName}`
              : 'Message'
            : 'Property Value';
      this.drawTextOverlay(state, label);
    }
  }

  private drawObject(
    obj: Pick<PeerState, 'x' | 'y' | 'nickname' | 'gender' | 'wornClothing'>,
    color: string,
    name: string,
  ): void {
    const drawX = obj.x * this.squarePixelSize;
    const drawY = this.canvas.height - (obj.y * this.squarePixelSize) - this.squarePixelSize;
    const size = this.squarePixelSize;
    const centerX = drawX + size / 2;
    const clothing = new Set(obj.wornClothing ?? []);
    const gender = (obj.gender ?? '').toLowerCase();
    this.ctx.fillStyle = gender.includes('woman') ? '#f9a8d4' : gender.includes('man') ? '#93c5fd' : color;
    this.ctx.beginPath();
    this.ctx.arc(centerX, drawY + size * 0.22, size * 0.16, 0, Math.PI * 2);
    this.ctx.fill();
    this.ctx.fillStyle = clothing.has('everyday-top') ? '#f59e0b' : '#d1d5db';
    this.ctx.fillRect(drawX + size * 0.28, drawY + size * 0.38, size * 0.44, size * 0.3);
    this.ctx.fillStyle = clothing.has('everyday-bottom') ? '#2563eb' : '#9ca3af';
    this.ctx.fillRect(drawX + size * 0.3, drawY + size * 0.7, size * 0.18, size * 0.22);
    this.ctx.fillRect(drawX + size * 0.52, drawY + size * 0.7, size * 0.18, size * 0.22);
    if (clothing.has('shoes')) {
      this.ctx.fillStyle = '#111827';
      this.ctx.fillRect(drawX + size * 0.25, drawY + size * 0.9, size * 0.24, size * 0.06);
      this.ctx.fillRect(drawX + size * 0.51, drawY + size * 0.9, size * 0.24, size * 0.06);
    }
    this.ctx.fillStyle = 'white';
    this.ctx.font = '12px Courier New';
    this.ctx.textAlign = 'center';
    const descriptor = obj.gender ? ` (${obj.gender}${clothing.size ? `, ${clothing.size} worn` : ''})` : '';
    this.ctx.fillText(`${name}${descriptor}`, drawX + this.squarePixelSize / 2, drawY - 5);
  }

  private drawTextOverlay(state: GameState, label: string): void {
    const { ctx } = this;
    ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
    ctx.fillRect(0, this.canvas.height / 2 - 30, this.canvas.width, 60);
    ctx.fillStyle = 'white';
    ctx.font = '24px Courier New';
    ctx.textAlign = 'center';

    const text = `${label}: ${state.nicknameInput}`;
    const textMetrics = ctx.measureText(text);
    const preCursorText = `${label}: ${state.nicknameInput.substring(0, state.cursorPos)}`;
    const preCursorWidth = ctx.measureText(preCursorText).width;
    const textX = this.canvas.width / 2;

    ctx.fillText(text, textX, this.canvas.height / 2);
    if (state.cursorVisible) {
      ctx.fillRect(textX - textMetrics.width / 2 + preCursorWidth, this.canvas.height / 2 - 20, 2, 24);
    }
  }

  private drawItem(item: WorldItem): void {
    const drawX = item.x * this.squarePixelSize;
    const drawY = this.canvas.height - (item.y * this.squarePixelSize) - this.squarePixelSize;
    this.ctx.fillStyle =
      item.type === 'radio_station'
        ? '#fbbf24'
        : item.type === 'house'
          ? '#fb7185'
          : item.type === 'house_alarm'
            ? '#ef4444'
          : item.type === 'house_keeper'
            ? '#34d399'
          : item.type === 'billboard'
            ? '#38bdf8'
        : item.type === 'wheel'
          ? '#f97316'
          : item.type === 'piano'
            ? '#c4b5fd'
          : item.type === 'clock'
            ? '#86efac'
            : item.type === 'widget'
              ? '#22d3ee'
              : '#60a5fa';
    this.ctx.fillRect(drawX, drawY, this.squarePixelSize, this.squarePixelSize);
    this.ctx.fillStyle = '#111827';
    this.ctx.font = 'bold 12px Courier New';
    this.ctx.textAlign = 'center';
    this.ctx.fillText(
      item.type === 'radio_station'
        ? 'R'
        : item.type === 'house'
          ? 'H'
          : item.type === 'house_alarm'
            ? 'A'
          : item.type === 'house_keeper'
            ? 'K'
          : item.type === 'billboard'
            ? 'B'
        : item.type === 'wheel'
          ? 'W'
          : item.type === 'piano'
            ? 'P'
          : item.type === 'clock'
            ? 'C'
            : item.type === 'widget'
              ? 'I'
              : 'D',
      drawX + this.squarePixelSize / 2,
      drawY + 13,
    );
  }
}
