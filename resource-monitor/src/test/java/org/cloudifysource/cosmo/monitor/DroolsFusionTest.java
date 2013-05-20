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
package org.cloudifysource.cosmo.monitor;

import java.util.Collection;
import java.util.Date;
import java.util.concurrent.TimeUnit;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyZeroInteractions;

import com.google.common.collect.Iterables;
import org.cloudifysource.cosmo.monitor.mock.AppInfo;
import org.cloudifysource.cosmo.monitor.mock.MonitoringMessage;
import org.drools.KnowledgeBase;
import org.drools.KnowledgeBaseConfiguration;
import org.drools.KnowledgeBaseFactory;
import org.drools.builder.KnowledgeBuilder;
import org.drools.builder.KnowledgeBuilderFactory;
import org.drools.builder.ResourceType;
import org.drools.conf.EventProcessingOption;
import org.drools.definition.KnowledgePackage;
import org.drools.io.ResourceFactory;
import org.drools.runtime.Channel;
import org.drools.runtime.KnowledgeSessionConfiguration;
import org.drools.runtime.StatefulKnowledgeSession;
import org.drools.runtime.conf.ClockTypeOption;
import org.drools.runtime.rule.WorkingMemoryEntryPoint;
import org.drools.time.SessionPseudoClock;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;

import static org.fest.assertions.api.Assertions.assertThat;

/**
 * A simple Drools Fusion example.
 * @since 0.1
 * @author Itai Frenkel
 */
public class DroolsFusionTest {

    public static final String RULE_FILE = "/org/cloudifysource/cosmo/monitor/DroolsFusionTest.drl";
    private KnowledgeBuilder kbuilder;
    private KnowledgeBase kbase;
    private StatefulKnowledgeSession ksession;
    private WorkingMemoryEntryPoint entryPoint;
    private SessionPseudoClock clock;
    private Channel exitChannel;

    @Test
    public void testEarlyMessageNotCorrelated() {
        fireAppInfo();

        entryPoint.insert(newMessage());
        fireAllRules();
        //assert no message fired through exit channel
        verifyZeroInteractions(exitChannel);
    }

    @Test
    public void testLateMessageCorrelated() {
        fireAppInfo();

        clock.advanceTime(1, TimeUnit.MINUTES);
        entryPoint.insert(newMessage());
        fireAllRules();

        //assert "after" message fired through exit channel
        MonitoringMessage afterMessage = newMessage("after");
        verify(exitChannel).send(afterMessage);
    }

    @Test
    public void testMissingMessageCorrelated() {

        MonitoringMessage requestMessage = newMessage("request");
        entryPoint.insert(requestMessage);
        clock.advanceTime(1, TimeUnit.MINUTES);

        fireAllRules();

        //assert "after" message fired through exit channel
        MonitoringMessage missingMessage = newMessage("missing");
        missingMessage.setTimestamp(null); // exitChannel should assign timestamp
        verify(exitChannel).send(missingMessage);
    }

    private void fireAppInfo() {
        AppInfo appInfo = new AppInfo();
        appInfo.setTimestamp(now());
        entryPoint.insert(appInfo);
        fireAllRules();
        verifyZeroInteractions(exitChannel);
    }

    private void fireAllRules() {
        ksession.fireAllRules();
    }

    private MonitoringMessage newMessage() {
        return newMessage("before");
    }
    private MonitoringMessage newMessage(String type) {
        MonitoringMessage beforeMessage = new MonitoringMessage();
        beforeMessage.setType(type);
        beforeMessage.setMsgtext("This is the message text");
        beforeMessage.setTimestamp(now());
        return beforeMessage;
    }

    private Date now() {
        return new Date(clock.getCurrentTime());
    }

    @BeforeMethod
    private void initDrools() {

        KnowledgeBaseConfiguration config = KnowledgeBaseFactory.newKnowledgeBaseConfiguration();
        // Stream mode allows interacting with the clock (Drools Fusion)
        config.setOption(EventProcessingOption.STREAM);
        kbase = KnowledgeBaseFactory.newKnowledgeBase(config);

        kbuilder = KnowledgeBuilderFactory.newKnowledgeBuilder();
        // this will parse and compile in one step
        kbuilder.add(ResourceFactory.newClassPathResource(RULE_FILE, DroolsFusionTest.class), ResourceType.DRL);

        // Check the builder for errors
        assertThat(kbuilder.hasErrors())
                .overridingErrorMessage(kbuilder.getErrors().toString())
                .isFalse();

        // get the compiled packages (which are serializable)
        Collection<KnowledgePackage> pkgs = kbuilder.getKnowledgePackages();

        // add the packages to a knowledgebase (deploy the knowledge packages).
        kbase.addKnowledgePackages(pkgs);

        KnowledgeSessionConfiguration conf = KnowledgeBaseFactory.newKnowledgeSessionConfiguration();
        conf.setOption(ClockTypeOption.get("pseudo"));
        ksession = kbase.newStatefulKnowledgeSession(conf, null);
        clock = ksession.getSessionClock();
        Collection<? extends WorkingMemoryEntryPoint> entryPoints = ksession.getWorkingMemoryEntryPoints();
        if (entryPoints.size() > 1) {
            throw new IllegalArgumentException("DRL file must use default entry point");
        }
        //entryPoint = ksession.getWorkingMemoryEntryPoint("input");
        entryPoint = Iterables.getOnlyElement(entryPoints);
        assertThat(entryPoint).isNotNull();
        exitChannel = mock(Channel.class);
        ksession.registerChannel("output", exitChannel);
    }

    @AfterMethod
    public void destroyDrools() {
        ksession.halt();
        ksession.dispose();
    }
}
