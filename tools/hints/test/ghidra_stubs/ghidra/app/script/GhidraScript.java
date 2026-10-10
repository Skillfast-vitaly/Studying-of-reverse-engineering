package ghidra.app.script;

import java.util.List;

import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Program;
import ghidra.util.task.TaskMonitor;

/** Заглушка: сигнатуры как в Ghidra 12.1.4 (GhidraScript и FlatProgramAPI). */
public abstract class GhidraScript {
	protected Program currentProgram;
	protected Address currentAddress;
	protected TaskMonitor monitor;

	public abstract void run() throws Exception;

	public void popup(final String message) {
	}

	public void println(String message) {
	}

	public <T> T askChoice(String title, String message, List<T> choices, T defaultValue)
			throws Exception {
		return defaultValue;
	}

	public final Function getFunctionContaining(Address address) {
		return null;
	}

	public final String getEOLComment(Address address) {
		return null;
	}

	public final boolean setEOLComment(Address address, String comment) {
		return true;
	}
}
