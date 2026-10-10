package ghidra.program.model.listing;

import ghidra.program.model.address.Address;

/** Заглушка: в Ghidra эти методы приходят из CodeUnit. */
public interface Instruction {
	String getMnemonicString();

	Address getAddress();
}
