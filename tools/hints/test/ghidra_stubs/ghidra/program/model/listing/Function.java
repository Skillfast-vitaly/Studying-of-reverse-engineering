package ghidra.program.model.listing;

import ghidra.program.model.address.AddressSetView;

/** Заглушка: в Ghidra getName и getBody приходят из Namespace. */
public interface Function {
	String getName();

	AddressSetView getBody();
}
