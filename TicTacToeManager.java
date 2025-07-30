import java.net.InetAddress;
import java.util.HashMap;
import java.util.Map;

public class TicTacToeManager {
    private static class GameState {
        String[] board = new String[9]; // 0–8
        String mySymbol;
        String currentTurnSymbol = "X";
        String opponent;
        String myUserId;
    }

    private static final Map<String, GameState> games = new HashMap<>();

    public static void handleInvite(String gameId, String from, String symbol, String myUserId) {
        GameState state = new GameState();
        state.mySymbol = symbol.equals("X") ? "O" : "X";
        state.opponent = from;
        state.myUserId = myUserId;
        games.put(gameId, state);

        String name = from.split("@")[0];
        System.out.println("\n" + name + " is inviting you to play tic-tac-toe.");
        printBoard(state.board);
    }

    public static void handleMove(String gameId, String symbol, int position, int turn) {
        GameState state = games.get(gameId);
        if (state == null) {
            state = new GameState(); // recovery mode
            games.put(gameId, state);
        }

        if (state.board[position] != null) {
            LSLogger.warn("Position " + position + " already taken.");
            return;
        }

        state.board[position] = symbol;
        state.currentTurnSymbol = symbol.equals("X") ? "O" : "X";

        System.out.println("\n[GAME: " + gameId + "] Turn " + turn);
        printBoard(state.board);

        if (checkWin(state.board, symbol)) {
            System.out.println(symbol + " wins!");
            if (symbol.equals(state.mySymbol)) {
                sendResult(gameId, "WIN", symbol, getWinningLine(state.board, symbol), state);
            } else {
                sendResult(gameId, "LOSS", symbol, getWinningLine(state.board, symbol), state);
            }
            games.remove(gameId);
        } else if (isDraw(state.board)) {
            System.out.println("Game is a draw.");
            sendResult(gameId, "DRAW", symbol, "", state);
            games.remove(gameId);
        } else {
            System.out.println("Next turn: " + state.currentTurnSymbol);
        }
    }

    public static void handleResult(String gameId, String result, String line, String symbol) {
        GameState state = games.get(gameId);
        System.out.println("\n[RESULT] Game " + gameId + ": " + result);
        if (state != null) {
            printBoard(state.board);
            if (!line.isEmpty()) {
                System.out.println("Winning Line: " + line);
            }
            games.remove(gameId);
        }
    }

    private static void printBoard(String[] board) {
        for (int i = 0; i < 9; i++) {
            String cell = board[i] != null ? board[i] : " ";
            System.out.print(" " + cell + " ");
            if (i % 3 != 2) System.out.print("|");
            if (i % 3 == 2 && i != 8) System.out.println("\n-----------");
        }
        System.out.println();
    }

    private static boolean checkWin(String[] board, String sym) {
        int[][] wins = {
            {0,1,2}, {3,4,5}, {6,7,8},
            {0,3,6}, {1,4,7}, {2,5,8},
            {0,4,8}, {2,4,6}
        };
        for (int[] line : wins) {
            if (sym.equals(board[line[0]]) &&
                sym.equals(board[line[1]]) &&
                sym.equals(board[line[2]])) {
                return true;
            }
        }
        return false;
    }

    private static boolean isDraw(String[] board) {
        for (String cell : board) {
            if (cell == null) return false;
        }
        return true;
    }

    private static String getWinningLine(String[] board, String sym) {
        int[][] wins = {
            {0,1,2}, {3,4,5}, {6,7,8},
            {0,3,6}, {1,4,7}, {2,5,8},
            {0,4,8}, {2,4,6}
        };
        for (int[] line : wins) {
            if (sym.equals(board[line[0]]) &&
                sym.equals(board[line[1]]) &&
                sym.equals(board[line[2]])) {
                return line[0] + "," + line[1] + "," + line[2];
            }
        }
        return "";
    }

    private static void sendResult(String gameId, String result, String symbol, String line, GameState state) {
        if (state == null) return;
        String from = state.myUserId;
        String to = state.opponent;
        String msg = String.join("\n",
            "TYPE: TICTACTOE_RESULT",
            "FROM: " + from,
            "TO: " + to,
            "GAMEID: " + gameId,
            "MESSAGE_ID: " + LSIPUtils.generateMessageId(),
            "RESULT: " + result,
            "SYMBOL: " + symbol,
            "WINNING_LINE: " + line,
            "TIMESTAMP: " + (System.currentTimeMillis() / 1000),
            ""
        );

        try {
            InetAddress ip = InetAddress.getByName(to.split("@")[1]);
            LSDatagramSender.sendCustomMessage(msg, ip);
        } catch (Exception e) {
            LSLogger.warn("Failed to send result: " + e.getMessage());
        }
    }
}