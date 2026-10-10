package ghidra.program.model.listing;

import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSetView;

/** Заглушка. */
public interface Listing {
	Instruction getInstructionContaining(Address addr);

	InstructionIterator getInstructions(AddressSetView addrSet, boolean forward);
}
