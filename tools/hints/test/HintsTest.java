import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.List;

/**
 * Проверка скриптов Ghidra без Ghidra: для каждой строки «мнемоника\tтекст»
 * печатает подсказку и короткий комментарий. build_hints.py сравнивает
 * это слово в слово с ответом плагина IDA (Python).
 */
public class HintsTest {
	public static void main(String[] args) throws Exception {
		PrintStream out = new PrintStream(System.out, true, StandardCharsets.UTF_8);
		boolean first = true;
		for (String line : Files.readAllLines(Paths.get(args[0]), StandardCharsets.UTF_8)) {
			String[] p = line.split("\t", 2);
			List<String> d = RuHintExplain.describe(p[0], p.length > 1 ? p[1] : "");
			String c = RuHintComments.shortComment(p[0], p.length > 1 ? p[1] : "");
			if (!first) {
				out.print("\n\u001e\n");
			}
			first = false;
			out.print((d == null ? "<null>" : String.join("\n", d)) + "\n"
				+ (c == null ? "<null>" : c));
		}
	}
}
