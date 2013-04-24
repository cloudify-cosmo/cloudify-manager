package org.cloudifysource.cosmo.cep.messages;

/**
 * A message sent from the agent to the resource monitor about a resource.
 * @author itaif
 * @since 0.1
 */
public class AgentStatusMessage {

    String agentId;

    public String getAgentId() {
        return agentId;
    }

    public void setAgentId(String agentId) {
        this.agentId = agentId;
    }


}
