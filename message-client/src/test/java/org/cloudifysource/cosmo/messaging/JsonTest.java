package org.cloudifysource.cosmo.messaging;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.cloudifysource.cosmo.messaging.messages.MockMessage;
import org.testng.annotations.Test;

import java.io.IOException;

import static org.fest.assertions.api.Assertions.assertThat;

/**
 * Tests JSON serialization/deserialization of messages.
 * @see MessageMixin
 */
public class JsonTest {

    @Test
    public void testSerialization() throws IOException {
        final ObjectMapper mapper = ObjectMapperFactory.newObjectMapper();
        final MockMessage message = new MockMessage();
        message.setValue(1);
        final String json = mapper.writerWithType(message.getClass()).writeValueAsString(message);
        final MockMessage message2 = (MockMessage) mapper.readValue(json, Object.class);
        assertThat(message2).isEqualTo(message);
    }
}
