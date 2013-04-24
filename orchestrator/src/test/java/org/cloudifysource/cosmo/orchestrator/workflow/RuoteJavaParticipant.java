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
package org.cloudifysource.cosmo.orchestrator.workflow;

import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * @author Idan Moyal
 * @since 0.1
 */
public class RuoteJavaParticipant {

    private static AtomicInteger executeInvocationsCounter = new AtomicInteger(0);

    public void execute(Map<String, Object> workItemFields) {
        System.out.println(getClass().getName() + ".execute() invoked");
        executeInvocationsCounter.incrementAndGet();
    }

    public static void reset() {
        executeInvocationsCounter.set(0);
    }

    public static int get() {
        return executeInvocationsCounter.get();
    }

}
