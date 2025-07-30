public class TicTacToeMessageBuilder {

    public static String buildInvite(String from, String to, String gameId, String symbol, String token) {
        return String.join("\n",
            "TYPE: TICTACTOE_INVITE",
            "FROM: " + from,
            "TO: " + to,
            "GAMEID: " + gameId,
            "SYMBOL: " + symbol,
            "TIMESTAMP: " + (System.currentTimeMillis() / 1000),
            "TOKEN: " + token,
            ""
        );
    }

    public static String buildMove(String from, String to, String gameId, int position, String symbol, int turn, String token) {
        return String.join("\n",
            "TYPE: TICTACTOE_MOVE",
            "FROM: " + from,
            "TO: " + to,
            "GAMEID: " + gameId,
            "POSITION: " + position,
            "SYMBOL: " + symbol,
            "TURN: " + turn,
            "TOKEN: " + token,
            ""
        );
    }
}