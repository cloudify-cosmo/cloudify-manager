/*******************************************************************************
 * Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *       http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *******************************************************************************/
package org.cloudifysource.cosmo.cep.mock;

import java.util.Date;

/**
 * A simple Drools Expert example POJO.
 * @since 0.1
 * @author Itai Frenkel
 */
public class MonitoringMessage {

    private String type;
    private String msgtext;
    private Date timestamp;

    /**
     * @return the type
     */
    public String getType() {
        return type;
    }

    /**
     * @param type the type to set
     */
    public void setType(String type) {
        this.type = type;
    }

    /**
     * @return the msgtext
     */
    public String getMsgtext() {
        return msgtext;
    }

    /**
     * @param msgtext the msgtext to set
     */
    public void setMsgtext(String msgtext) {
        this.msgtext = msgtext;
    }

    public Date getTimestamp() {
        return timestamp;
    }

    public void setTimestamp(Date timestamp) {
        this.timestamp = timestamp;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof MonitoringMessage)) return false;

        MonitoringMessage message = (MonitoringMessage) o;

        if (msgtext != null ? !msgtext.equals(message.msgtext) : message.msgtext != null) return false;
        if (timestamp != null ? !timestamp.equals(message.timestamp) : message.timestamp != null) return false;
        if (type != null ? !type.equals(message.type) : message.type != null) return false;

        return true;
    }

    @Override
    public int hashCode() {
        int result = type != null ? type.hashCode() : 0;
        result = 31 * result + (msgtext != null ? msgtext.hashCode() : 0);
        result = 31 * result + (timestamp != null ? timestamp.hashCode() : 0);
        return result;
    }

    @Override
    public String toString() {
        return "MonitoringMessage{" +
                "type='" + type + '\'' +
                ", msgtext='" + msgtext + '\'' +
                ", timestamp=" + timestamp +
                '}';
    }
}
