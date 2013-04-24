package org.cloudifysource.cosmo.agent.messages;

/**
 * A message sent from the resource monitor to the agent.
 *
 * @author itaif
 * @since 0.1
 */
public class ProbeAgentMessage {

    String agentId;

    public ProbeAgentMessage() {

    }

    public String getAgentId() {
        return agentId;
    }

    public void setAgentId(String agentId) {
        this.agentId = agentId;
    }
}
