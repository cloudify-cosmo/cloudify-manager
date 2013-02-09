package org.openspaces.servicegrid.state;

public class EtagPreconditionNotMetException extends RuntimeException {

	private static final long serialVersionUID = 1L;
	private Etag actual;
	private Etag expected;

	public EtagPreconditionNotMetException(Etag actual, Etag expected) {
		super(String.format("Etag mismatch. Expected %s. Actual %s",expected, actual));
		this.actual = actual;
		this.expected = expected;
	}

	public Etag getActualEtag() {
		return actual;
	}

	public Etag getExpectedEtag() {
		return expected;
	}
}
