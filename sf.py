#!/usr/bin/env python3
"""
Features:
- Click source then destination to make a move
- Visual feedback for legal moves
- "Engine Move" asks Stockfish for a best move
- "Analyze" runs analysis with evaluation
- New Game, Undo, Flip Board
- Load/Save FEN and PGN support
"""
import os
import threading
import tkinter as tk
from tkinter import simpledialog, messagebox, filedialog
import shutil
import chess
import chess.engine
import chess.pgn
from datetime import datetime

# === Configuration ===
DEFAULT_ENGINE = "bin/stockfish"

SQUARE_SIZE = 64
EVAL_BAR_WIDTH = 30
BOARD_COLOR_1 = "#EEEED2"
BOARD_COLOR_2 = "#769656"
HIGHLIGHT_COLOR = "#BACA44"
LEGAL_MOVE_COLOR = "#90EE90"
LAST_MOVE_COLOR = "#CDD26A"
PIECE_FONT = ("DejaVu Sans", 40)

# Eval bar colors
EVAL_WHITE_COLOR = "#E0E0E0"
EVAL_BLACK_COLOR = "#000000"
EVAL_TEXT_COLOR = "#888888"

UNICODE_PIECES = {
    'P': '♙', 'N': '♘', 'B': '♗', 'R': '♖', 'Q': '♕', 'K': '♔',
    'p': '♟', 'n': '♞', 'b': '♝', 'r': '♜', 'q': '♛', 'k': '♚'
}


class StockfishGUI(tk.Tk):
    def __init__(self, engine_path=DEFAULT_ENGINE):
        super().__init__()
        self.title("Stockfish GUI")
        self.engine_path = engine_path
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Set background color
        self.configure(bg="#808080")

        # Chess state
        self.board = chess.Board()
        self.selected = None
        self.last_move = None
        self.flipped = False
        self.engine = None
        self.engine_thinking = False
        self.current_eval = None  # Stores current evaluation
        self.auto_analyze = tk.BooleanVar(value=True)  # Auto-analysis toggle

        # UI Setup
        self._setup_ui()
        self.draw_board()

    def _setup_ui(self):
        """Initialize all UI components"""
        # Main container for board and eval bar
        board_frame = tk.Frame(self, bg="#E0E0E0")
        board_frame.grid(row=0, column=0, columnspan=6, padx=5, pady=5)
        
        # Eval bar canvas (left side)
        self.eval_canvas = tk.Canvas(
            board_frame,
            width=EVAL_BAR_WIDTH,
            height=SQUARE_SIZE*8,
            highlightthickness=0,
            bg="#E0E0E0"
        )
        self.eval_canvas.pack(side=tk.LEFT, padx=(0, 5))
        
        # Main board canvas
        self.canvas = tk.Canvas(
            board_frame, 
            width=SQUARE_SIZE*8, 
            height=SQUARE_SIZE*8,
            highlightthickness=0
        )
        self.canvas.pack(side=tk.LEFT)
        self.canvas.bind("<Button-1>", self.on_click)

        # Control buttons row 1
        btn_frame1 = tk.Frame(self, bg="#E0E0E0")
        btn_frame1.grid(row=1, column=0, columnspan=6, pady=5)
        
        tk.Button(btn_frame1, text="Engine Move", command=self.do_engine_move, width=12).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame1, text="Analyze", command=self.do_analyze, width=12).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame1, text="New Game", command=self.new_game, width=12).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame1, text="Undo", command=self.undo, width=12).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame1, text="Flip Board", command=self.flip_board, width=12).pack(side=tk.LEFT, padx=2)

        # Control buttons row 2
        btn_frame2 = tk.Frame(self, bg="#E0E0E0")
        btn_frame2.grid(row=2, column=0, columnspan=6, pady=5)
        
        tk.Button(btn_frame2, text="Load FEN", command=self.load_fen, width=12).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame2, text="Save FEN", command=self.save_fen, width=12).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame2, text="Load PGN", command=self.load_pgn, width=12).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame2, text="Save PGN", command=self.save_pgn, width=12).pack(side=tk.LEFT, padx=2)

        # Engine settings
        settings_frame = tk.Frame(self, bg="#E0E0E0")
        settings_frame.grid(row=3, column=0, columnspan=6, pady=5)
        
        tk.Label(settings_frame, text="Depth:", bg="#E0E0E0").pack(side=tk.LEFT, padx=2)
        self.depth_var = tk.IntVar(value=18)
        tk.Spinbox(settings_frame, from_=1, to=40, textvariable=self.depth_var, width=5).pack(side=tk.LEFT, padx=2)
        
        tk.Checkbutton(settings_frame, text="Auto-Analyze", variable=self.auto_analyze, 
                      bg="#E0E0E0", command=self.toggle_auto_analyze).pack(side=tk.LEFT, padx=10)
        
        tk.Label(settings_frame, text="Engine:", bg="#E0E0E0").pack(side=tk.LEFT, padx=(10, 2))
        self.engine_entry = tk.Entry(settings_frame, width=30)
        self.engine_entry.pack(side=tk.LEFT, padx=2)
        self.engine_entry.insert(0, self.engine_path)
        tk.Button(settings_frame, text="Set Path", command=self.set_engine_path).pack(side=tk.LEFT, padx=2)

        # Status bar
        self.status = tk.StringVar(value="Ready")
        status_label = tk.Label(self, textvariable=self.status, anchor="w", relief=tk.SUNKEN, bd=1, bg="#F0F0F0")
        status_label.grid(row=4, column=0, columnspan=6, sticky="we", padx=5, pady=5)

        # Move list
        move_frame = tk.Frame(self, bg="#E0E0E0")
        move_frame.grid(row=5, column=0, columnspan=6, sticky="nsew", padx=5, pady=5)
        
        tk.Label(move_frame, text="Moves:", bg="#E0E0E0").pack(anchor="w")
        
        self.move_text = tk.Text(move_frame, height=6, width=60, wrap=tk.WORD)
        self.move_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(move_frame, command=self.move_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.move_text.config(yscrollcommand=scrollbar.set)

    def draw_board(self):
        """Redraw the entire board"""
        self.canvas.delete("all")
        
        # Draw squares
        for r in range(8):
            for c in range(8):
                self._draw_square(c, r)
        
        # Highlight last move
        if self.last_move:
            self._highlight_square(chess.square_file(self.last_move.from_square), 
                                  chess.square_rank(self.last_move.from_square), 
                                  LAST_MOVE_COLOR)
            self._highlight_square(chess.square_file(self.last_move.to_square), 
                                  chess.square_rank(self.last_move.to_square), 
                                  LAST_MOVE_COLOR)
        
        # Highlight selected square and legal moves
        if self.selected is not None:
            c, r = self.selected
            self._highlight_square(c, r, HIGHLIGHT_COLOR)
            self._show_legal_moves(c, r)
        
        # Draw pieces
        for sq in chess.SQUARES:
            piece = self.board.piece_at(sq)
            if piece:
                file = chess.square_file(sq)
                rank = chess.square_rank(sq)
                self._draw_piece(file, rank, piece)
        
        # Update move list
        self._update_move_list()
        
        # Update eval bar
        self._draw_eval_bar()
        
        # Update status
        self._update_status()

    def _draw_square(self, c, r):
        """Draw a single square on the board"""
        x0, y0 = self._get_screen_coords(c, r)
        color = BOARD_COLOR_1 if (r + c) % 2 == 0 else BOARD_COLOR_2
        self.canvas.create_rectangle(
            x0, y0, x0 + SQUARE_SIZE, y0 + SQUARE_SIZE, 
            fill=color, outline="", tags="square"
        )

    def _highlight_square(self, c, r, color):
        """Highlight a square with the given color"""
        x0, y0 = self._get_screen_coords(c, r)
        self.canvas.create_rectangle(
            x0, y0, x0 + SQUARE_SIZE, y0 + SQUARE_SIZE,
            outline=color, width=4, tags="highlight"
        )

    def _show_legal_moves(self, c, r):
        """Show legal move indicators for selected piece"""
        src = chess.square(c, r)
        for move in self.board.legal_moves:
            if move.from_square == src:
                dest_file = chess.square_file(move.to_square)
                dest_rank = chess.square_rank(move.to_square)
                x0, y0 = self._get_screen_coords(dest_file, dest_rank)
                
                # Draw circle for legal moves
                center_x = x0 + SQUARE_SIZE // 2
                center_y = y0 + SQUARE_SIZE // 2
                radius = 8
                
                # Check if this is a capture (including en passant)
                is_capture = self.board.is_capture(move)
                
                if is_capture:
                    # Capture indicator (ring around edge)
                    self.canvas.create_oval(
                        x0 + 2, y0 + 2, x0 + SQUARE_SIZE - 2, y0 + SQUARE_SIZE - 2,
                        outline=LEGAL_MOVE_COLOR, width=4, tags="legal"
                    )
                else:
                    # Normal move indicator (small circle)
                    self.canvas.create_oval(
                        center_x - radius, center_y - radius,
                        center_x + radius, center_y + radius,
                        fill=LEGAL_MOVE_COLOR, outline="", tags="legal"
                    )

    def _draw_piece(self, file, rank, piece):
        """Draw a piece on the board"""
        x0, y0 = self._get_screen_coords(file, rank)
        x = x0 + SQUARE_SIZE // 2
        y = y0 + SQUARE_SIZE // 2
        text = UNICODE_PIECES[piece.symbol()]
        self.canvas.create_text(x, y, text=text, font=PIECE_FONT, tags="piece")

    def _get_screen_coords(self, file, rank):
        """Convert board coordinates to screen coordinates"""
        if self.flipped:
            x0 = (7 - file) * SQUARE_SIZE
            y0 = rank * SQUARE_SIZE
        else:
            x0 = file * SQUARE_SIZE
            y0 = (7 - rank) * SQUARE_SIZE
        return x0, y0

    def _get_board_coords(self, x, y):
        """Convert screen coordinates to board coordinates"""
        c = x // SQUARE_SIZE
        r = 7 - (y // SQUARE_SIZE)
        
        if self.flipped:
            c = 7 - c
            r = 7 - r
        
        if 0 <= c < 8 and 0 <= r < 8:
            return c, r
        return None

    def _update_move_list(self):
        """Update the move list display"""
        self.move_text.delete(1.0, tk.END)
        moves = list(self.board.move_stack)
        
        if not moves:
            self.move_text.insert(tk.END, "No moves yet.")
            return
        
        b = chess.Board()
        move_str = ""
        for i, m in enumerate(moves):
            if i % 2 == 0:
                move_str += f"{(i//2)+1}. "
            move_str += b.san(m) + " "
            b.push(m)
            if (i + 1) % 2 == 0:
                move_str += "\n"
        
        self.move_text.insert(tk.END, move_str)
        self.move_text.see(tk.END)

    def _update_status(self):
        """Update status bar with game information"""
        if self.engine_thinking:
            return  # Don't overwrite thinking status
        
        if self.board.is_checkmate():
            winner = "Black" if self.board.turn else "White"
            self.status.set(f"Checkmate! {winner} wins!")
        elif self.board.is_stalemate():
            self.status.set("Stalemate!")
        elif self.board.is_insufficient_material():
            self.status.set("Draw by insufficient material")
        elif self.board.is_check():
            self.status.set("Check!")
        else:
            turn = "White" if self.board.turn else "Black"
            eval_str = ""
            if self.current_eval:
                eval_str = f" | Eval: {self._format_eval(self.current_eval)}"
            self.status.set(f"{turn} to move | Moves: {len(self.board.move_stack)}{eval_str}")

    def _format_eval(self, score):
        """Format evaluation score for display"""
        # Convert PovScore to white's perspective
        score_white = score.white()
        
        if score_white.is_mate():
            mate_in = score_white.mate()
            return f"M{mate_in}" if mate_in > 0 else f"-M{abs(mate_in)}"
        else:
            # Convert centipawns to pawns
            cp = score_white.score()
            if cp is None:
                return "0.0"
            return f"{cp/100:+.1f}"

    def _draw_eval_bar(self):
        """Draw the evaluation bar"""
        self.eval_canvas.delete("all")
        
        board_height = SQUARE_SIZE * 8
        center_y = board_height // 2
        
        if self.current_eval is None:
            # Draw neutral bar (50/50)
            self.eval_canvas.create_rectangle(
                0, 0, EVAL_BAR_WIDTH, center_y,
                fill=EVAL_BLACK_COLOR, outline=""
            )
            self.eval_canvas.create_rectangle(
                0, center_y, EVAL_BAR_WIDTH, board_height,
                fill=EVAL_WHITE_COLOR, outline=""
            )
            # Draw center line
            self.eval_canvas.create_line(
                0, center_y, EVAL_BAR_WIDTH, center_y,
                fill="#888888", width=1
            )
            return
        
        # Convert PovScore to white's perspective
        score_white = self.current_eval.white()
        
        # Calculate bar percentage based on evaluation
        if score_white.is_mate():
            mate_in = score_white.mate()
            # Mate score: full bar for the winning side
            if mate_in > 0:
                white_percentage = 100
            else:
                white_percentage = 0
        else:
            cp = score_white.score()
            if cp is None:
                cp = 0
            
            # Improved evaluation bar calculation
            # Uses a more gradual sigmoid curve for better visual representation
            # Based on common chess engine evaluation bars
            
            # Clamp to reasonable range for visualization
            cp_clamped = max(-1500, min(1500, cp))
            
            # Sigmoid-like transformation
            # This makes:
            # - cp=0 -> 50%
            # - cp=+100 (1 pawn) -> ~57%
            # - cp=+300 (3 pawns) -> ~70%
            # - cp=+600 -> ~85%
            # - cp=+1000 -> ~95%
            win_probability = 50 + 50 * (2 / (1 + pow(10, -cp_clamped / 400)) - 1)
            white_percentage = max(0, min(100, win_probability))
        
        # Calculate heights
        white_height = int(board_height * white_percentage / 100)
        black_height = board_height - white_height
        
        # Draw black portion (top)
        if black_height > 0:
            self.eval_canvas.create_rectangle(
                0, 0, EVAL_BAR_WIDTH, black_height,
                fill=EVAL_BLACK_COLOR, outline=""
            )
        
        # Draw white portion (bottom)
        if white_height > 0:
            self.eval_canvas.create_rectangle(
                0, black_height, EVAL_BAR_WIDTH, board_height,
                fill=EVAL_WHITE_COLOR, outline=""
            )
        
        # Draw center line for reference
        self.eval_canvas.create_line(
            0, center_y, EVAL_BAR_WIDTH, center_y,
            fill="#666666", width=1
        )
        
        # Draw evaluation text
        eval_text = self._format_eval(self.current_eval)
        
        # Determine text position and color based on evaluation
        if white_percentage > 60:
            # White is winning significantly - put text in white area
            text_y = black_height + white_height // 2
            text_color = "#404040"
        elif white_percentage < 40:
            # Black is winning significantly - put text in black area
            text_y = black_height // 2
            text_color = "#C0C0C0"
        else:
            # Close to equal - put text near center on larger side
            if white_percentage >= 50:
                text_y = black_height + white_height // 2
                text_color = "#404040"
            else:
                text_y = black_height // 2
                text_color = "#C0C0C0"
        
        # Draw text with background for better readability
        text_id = self.eval_canvas.create_text(
            EVAL_BAR_WIDTH // 2, text_y,
            text=eval_text,
            font=("Arial", 9, "bold"),
            fill=text_color
        )
        
        # Add border to eval bar
        self.eval_canvas.create_rectangle(
            0, 0, EVAL_BAR_WIDTH, board_height,
            outline="#999999", width=1
        )

    def on_click(self, event):
        """Handle mouse clicks on the board"""
        coords = self._get_board_coords(event.x, event.y)
        if not coords:
            return
        
        c, r = coords
        sq = chess.square(c, r)
        piece = self.board.piece_at(sq)
        
        if self.selected is None:
            # Select piece
            if piece and piece.color == self.board.turn:
                self.selected = (c, r)
        else:
            # Try to make move
            src = chess.square(self.selected[0], self.selected[1])
            dest = sq
            
            if self._try_move(src, dest):
                self.selected = None
            else:
                # If clicked on own piece, change selection
                if piece and piece.color == self.board.turn:
                    self.selected = (c, r)
                else:
                    self.selected = None
        
        self.draw_board()

    def _try_move(self, src, dest):
        """Try to make a move, handling promotions"""
        # Check if this is a promotion move first
        piece = self.board.piece_at(src)
        needs_promotion = False
        
        if piece and piece.piece_type == chess.PAWN:
            # Check if pawn is moving to last rank
            dest_rank = chess.square_rank(dest)
            if (piece.color == chess.WHITE and dest_rank == 7) or \
               (piece.color == chess.BLACK and dest_rank == 0):
                needs_promotion = True
        
        if needs_promotion:
            # Ask for promotion piece
            promotion_piece = self._ask_promotion()
            if promotion_piece is None:
                return False  # User cancelled
            
            move = chess.Move(src, dest, promotion=promotion_piece)
            if move in self.board.legal_moves:
                self.board.push(move)
                self.last_move = move
                self.current_eval = None
                
                # Auto-analyze if enabled
                if self.auto_analyze.get():
                    self.after(100, self._quick_analyze)
                
                return True
            return False
        else:
            # Try normal move (includes castling and en passant)
            move = chess.Move(src, dest)
            if move in self.board.legal_moves:
                self.board.push(move)
                self.last_move = move
                self.current_eval = None
                
                # Auto-analyze if enabled
                if self.auto_analyze.get():
                    self.after(100, self._quick_analyze)
                
                return True
        
        return False
    
    def _ask_promotion(self):
        """Show dialog to select promotion piece - FIXED VERSION"""
        dialog = tk.Toplevel(self)
        dialog.title("Promote Pawn")
        dialog.configure(bg="#E0E0E0")
        dialog.transient(self)
        dialog.resizable(False, False)
        
        selected_piece = [None]  # Use list to store result
        
        tk.Label(dialog, text="Select promotion piece:", 
                font=("Arial", 12), bg="#E0E0E0").pack(pady=15, padx=20)
        
        button_frame = tk.Frame(dialog, bg="#E0E0E0")
        button_frame.pack(pady=10, padx=20)
        
        def select_piece(piece):
            selected_piece[0] = piece
            dialog.destroy()
        
        # Create buttons with unicode pieces - all four promotion options
        pieces = [
            (chess.QUEEN, "♕ Queen", "Q"),
            (chess.ROOK, "♖ Rook", "R"),
            (chess.BISHOP, "♗ Bishop", "B"),
            (chess.KNIGHT, "♘ Knight", "N")
        ]
        
        for piece_type, label, _ in pieces:
            btn = tk.Button(
                button_frame,
                text=label,
                font=("DejaVu Sans", 14),
                width=10,
                command=lambda p=piece_type: select_piece(p)
            )
            btn.pack(side=tk.LEFT, padx=5)
        
        # Handle window close - default to Queen
        dialog.protocol("WM_DELETE_WINDOW", lambda: select_piece(chess.QUEEN))
        
        # Center the dialog - do this AFTER creating all widgets
        dialog.update_idletasks()
        
        # Calculate position to center on parent
        parent_x = self.winfo_x()
        parent_y = self.winfo_y()
        parent_width = self.winfo_width()
        parent_height = self.winfo_height()
        
        dialog_width = dialog.winfo_reqwidth()
        dialog_height = dialog.winfo_reqheight()
        
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2
        
        dialog.geometry(f"+{x}+{y}")
        
        # IMPORTANT: Set grab AFTER window is positioned and visible
        dialog.deiconify()  # Ensure window is visible
        dialog.update()  # Process all pending events
        
        try:
            dialog.grab_set()  # Now grab should work
        except tk.TclError:
            pass  # If grab fails, continue anyway
        
        dialog.focus_set()
        
        # Wait for dialog to close
        self.wait_window(dialog)
        
        return selected_piece[0]

    def flip_board(self):
        """Flip the board orientation"""
        self.flipped = not self.flipped
        self.draw_board()

    def ensure_engine(self):
        """Ensure engine is loaded and ready"""
        if self.engine is not None:
            return True

        path = self.engine_entry.get().strip() or self.engine_path
        if not path:
            messagebox.showerror("Engine not set", 
                               "Set the engine path first (stockfish binary).")
            return False

        if not shutil.which("stockfish") and (not os.path.isfile(path) or not os.access(path, os.X_OK)):
            messagebox.showerror("Engine not executable",
                               f"Stockfish binary not found or not executable at:\n{path}")
            return False

        try:
            self.engine = chess.engine.SimpleEngine.popen_uci(path)
            return True
        except Exception as e:
            messagebox.showerror("Engine error", 
                               f"Failed to start engine at {path}\n\n{e}")
            return False

    def do_engine_move(self):
        """Request engine to make a move"""
        if self.engine_thinking:
            return
        
        if not self.ensure_engine():
            return
        
        if self.board.is_game_over():
            messagebox.showinfo("Game Over", "The game is already over!")
            return
        
        depth = int(self.depth_var.get())
        self.status.set("Engine thinking...")
        self.engine_thinking = True
        threading.Thread(target=self._engine_move_thread, args=(depth,), daemon=True).start()

    def _engine_move_thread(self, depth):
        """Engine move calculation thread"""
        try:
            limit = chess.engine.Limit(depth=depth)
            result = self.engine.play(self.board, limit)
            
            if result and result.move:
                self.board.push(result.move)
                self.last_move = result.move
                self.selected = None
                
                # Get evaluation after move (always for engine moves)
                info = self.engine.analyse(self.board, chess.engine.Limit(depth=min(depth, 15)))
                self.current_eval = info.get("score")
                
                self.after(0, self.draw_board)
                self.after(0, lambda: self.status.set(f"Engine played: {result.move}"))
            else:
                self.after(0, lambda: self.status.set("Engine returned no move."))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Engine error", str(e)))
            self.after(0, lambda: self.status.set("Engine failed."))
        finally:
            self.engine_thinking = False

    def do_analyze(self):
        """Run engine analysis"""
        if self.engine_thinking:
            return
        
        if not self.ensure_engine():
            return
        
        depth = int(self.depth_var.get())
        self.status.set("Analyzing...")
        self.engine_thinking = True
        threading.Thread(target=self._analyze_thread, args=(depth,), daemon=True).start()

    def _analyze_thread(self, depth):
        """Engine analysis thread"""
        try:
            info = self.engine.analyse(self.board, chess.engine.Limit(depth=depth))
            score = info.get("score")
            self.current_eval = score
            pv = info.get("pv", [])
            
            pv_str = " ".join(str(m) for m in pv[:5]) if pv else "None"
            eval_str = self._format_eval(score) if score else "N/A"
            txt = f"Evaluation: {eval_str} | Best line: {pv_str}"
            
            self.after(0, self.draw_board)
            self.after(0, lambda: self.status.set(txt))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Engine error", str(e)))
            self.after(0, lambda: self.status.set("Analysis failed."))
        finally:
            self.engine_thinking = False

    def _quick_analyze(self):
        """Quick analysis for auto-analyze feature (lower depth)"""
        if self.engine_thinking or not self.ensure_engine():
            return
        
        # Use lower depth for quick analysis (depth 15)
        quick_depth = min(15, int(self.depth_var.get()))
        self.engine_thinking = True
        threading.Thread(target=self._quick_analyze_thread, args=(quick_depth,), daemon=True).start()

    def _quick_analyze_thread(self, depth):
        """Quick analysis thread"""
        try:
            info = self.engine.analyse(self.board, chess.engine.Limit(depth=depth))
            score = info.get("score")
            self.current_eval = score
            self.after(0, self.draw_board)
        except Exception:
            pass  # Silently fail for auto-analysis
        finally:
            self.engine_thinking = False

    def toggle_auto_analyze(self):
        """Toggle auto-analysis on/off"""
        if self.auto_analyze.get():
            if not self.ensure_engine():
                self.auto_analyze.set(False)
                return
            # Run initial analysis
            self._quick_analyze()

    def new_game(self):
        """Start a new game"""
        if messagebox.askyesno("New Game", "Start a new game?"):
            self.board = chess.Board()
            self.selected = None
            self.last_move = None
            self.current_eval = None
            self.draw_board()

    def undo(self):
        """Undo last move"""
        if self.board.move_stack:
            self.board.pop()
            self.last_move = self.board.peek() if self.board.move_stack else None
            self.selected = None
            self.current_eval = None
            self.draw_board()
            
            # Auto-analyze if enabled
            if self.auto_analyze.get():
                self.after(100, self._quick_analyze)

    def load_fen(self):
        """Load position from FEN"""
        s = simpledialog.askstring("Load FEN", "Enter FEN string:", 
                                   initialvalue=self.board.fen())
        if s:
            try:
                self.board = chess.Board(fen=s)
                self.selected = None
                self.last_move = None
                self.current_eval = None
                self.draw_board()
            except Exception as e:
                messagebox.showerror("Invalid FEN", str(e))

    def save_fen(self):
        """Save current position as FEN"""
        fen = self.board.fen()
        try:
            self.clipboard_clear()
            self.clipboard_append(fen)
            messagebox.showinfo("FEN Saved", f"FEN copied to clipboard:\n\n{fen}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy to clipboard:\n{e}")

    def load_pgn(self):
        """Load game from PGN file"""
        filename = filedialog.askopenfilename(
            title="Load PGN",
            filetypes=[("PGN files", "*.pgn"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, "r") as f:
                    game = chess.pgn.read_game(f)
                    if game:
                        self.board = game.board()
                        for move in game.mainline_moves():
                            self.board.push(move)
                        self.last_move = self.board.peek() if self.board.move_stack else None
                        self.selected = None
                        self.current_eval = None
                        self.draw_board()
                    else:
                        messagebox.showerror("Error", "No game found in PGN file")
            except Exception as e:
                messagebox.showerror("Error loading PGN", str(e))

    def save_pgn(self):
        """Save game to PGN file"""
        filename = filedialog.asksaveasfilename(
            title="Save PGN",
            defaultextension=".pgn",
            filetypes=[("PGN files", "*.pgn"), ("All files", "*.*")]
        )
        if filename:
            try:
                game = chess.pgn.Game()
                game.headers["Event"] = "Casual Game"
                game.headers["Date"] = datetime.now().strftime("%Y.%m.%d")
                
                node = game
                board = chess.Board()
                for move in self.board.move_stack:
                    node = node.add_variation(move)
                    board.push(move)
                
                with open(filename, "w") as f:
                    f.write(str(game))
                
                messagebox.showinfo("Success", f"Game saved to {filename}")
            except Exception as e:
                messagebox.showerror("Error saving PGN", str(e))

    def set_engine_path(self):
        """Set the engine path"""
        path = self.engine_entry.get().strip()
        if not path:
            messagebox.showerror("Path empty", "Please enter the stockfish executable path.")
            return
        
        self.engine_path = path
        
        # Restart engine if already running
        if self.engine:
            try:
                self.engine.quit()
            except Exception:
                pass
            self.engine = None
        
        messagebox.showinfo("Engine set", f"Engine path set to: {path}")

    def on_close(self):
        """Clean up on window close"""
        if self.engine:
            try:
                self.engine.quit()
            except Exception:
                pass
        self.destroy()


if __name__ == "__main__":
    app = StockfishGUI()
    app.mainloop()
