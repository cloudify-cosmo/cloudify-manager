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
package org.cloudifysource.cosmo.resource.monitor;

import java.util.Collection;

import com.google.common.collect.Iterables;
import org.drools.KnowledgeBase;
import org.drools.KnowledgeBaseFactory;
import org.drools.builder.KnowledgeBuilder;
import org.drools.builder.KnowledgeBuilderFactory;
import org.drools.builder.ResourceType;
import org.drools.common.InternalFactHandle;
import org.drools.definition.KnowledgePackage;
import org.drools.io.ResourceFactory;
import org.drools.runtime.StatefulKnowledgeSession;
import org.drools.runtime.rule.FactHandle;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;

import static org.fest.assertions.api.Assertions.assertThat;

/**
 * A simple Drools Expert example.
 * @since 0.1
 * @author Itai Frenkel
 */
public class DroolsExpertTest {

    public static final String RULE_FILE = "/hellodrools/testrules.drl";
    private KnowledgeBuilder kbuilder = KnowledgeBuilderFactory.newKnowledgeBuilder();
    private Collection<KnowledgePackage> pkgs;
    private KnowledgeBase kbase = KnowledgeBaseFactory.newKnowledgeBase();
    private StatefulKnowledgeSession ksession;

    @Test
    public void testDrools() {
        Message beforeMessage = new Message();
        beforeMessage.setType("before");
        beforeMessage.setMsgtext("This is the message text");
        ksession.insert(beforeMessage);
        ksession.fireAllRules();
        final Message afterMessage = getMessageFromSession();
        assertThat(afterMessage.getType()).isEqualTo("after");
    }

    private Message getMessageFromSession() {
        final Collection<FactHandle> factHandles = ksession.getFactHandles();
        final InternalFactHandle fh = (InternalFactHandle) Iterables.getOnlyElement(factHandles);
        final Message message = ((Message) fh.getObject());
        return message;
    }

    @BeforeMethod
    private void initDrools() {

        // this will parse and compile in one step
        // read from file
        kbuilder.add(ResourceFactory.newClassPathResource(RULE_FILE, DroolsExpertTest.class), ResourceType.DRL);

        // Check the builder for errors
        assertThat(kbuilder.hasErrors()).overridingErrorMessage(kbuilder.getErrors().toString()).isFalse();

        // get the compiled packages (which are serializable)
        pkgs = kbuilder.getKnowledgePackages();

        // add the packages to a knowledgebase (deploy the knowledge packages).
        kbase.addKnowledgePackages(pkgs);

        ksession = kbase.newStatefulKnowledgeSession();
    }

    @AfterMethod
    public void destroyDrools() {
        ksession.halt();
        ksession.dispose();
    }
}
