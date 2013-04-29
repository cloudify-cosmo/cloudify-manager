package org.cloudifysource.cosmo.messaging.messages;
/**
 * Mock Message used by {@link org.cloudifysource.cosmo.messaging.JsonTest}
 *
 * @author itaif
 * @since 0.1
 */
public class MockMessage {

    int value;

    public int getValue() {
        return value;
    }

    public void setValue(int value) {
        this.value = value;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof MockMessage)) return false;

        MockMessage that = (MockMessage) o;

        if (value != that.value) return false;

        return true;
    }

    @Override
    public int hashCode() {
        return value;
    }
}
