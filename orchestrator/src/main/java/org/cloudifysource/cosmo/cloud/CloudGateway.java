/*
 * Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *       http://www.apache.org/licenses/LICENSE-2.0
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package org.cloudifysource.cosmo.cloud;

import com.google.common.base.Optional;
import com.google.common.base.Predicate;
import org.jclouds.compute.RunNodesException;
import org.jclouds.compute.domain.ComputeMetadata;
import org.jclouds.compute.domain.NodeMetadata;

/**
 * TODO: Write a short summary of this type's roles and responsibilities.
 *
 * @author Niv Ingberg
 * @since 0.1
 */
public class CloudGateway {

    private final CloudDriver driver;

    public CloudGateway(CloudDriver driver) {
        this.driver = driver;
    }

    public void close() {
        driver.close();
    }

    public NodeMetadata ensureStarted(String name) throws RunNodesException {
        final Optional<NodeMetadata> node = getByName(name);
        if (!node.isPresent())
            return driver.create(name);

        final NodeMetadata.Status status = node.get().getStatus();
        switch (status) {
            case RUNNING:
                return node.get();
            case SUSPENDED:
                driver.resume(node.get());
                return driver.searchNodeById(node.get().getId()).get();
            case PENDING:
                // TODO: wait for new node state to settle.
                throw new IllegalStateException("Node '" + name + "' is in PENDING status");
            case TERMINATED:
                // This state is illegal since terminated nodes should be filtered in getByName()
                throw new IllegalStateException("Node '" + name + "' is in TERMINATED status");
            case ERROR:
                throw new IllegalStateException("Node '" + name + "' is in ERROR status");
            case UNRECOGNIZED:
                throw new IllegalStateException("Node '" + name + "' is in UNRECOGNIZED status");
            default:
                throw new IllegalStateException("Node '" + name + "' is in unrecognized status: " + status);
        }
    }

    public void ensureDestoryed(String name) {
        final Optional<NodeMetadata> node = getByName(name);
        if (node.isPresent())
            driver.destroy(node.get());
    }

    private Optional<NodeMetadata> getByName(String name) {
        Predicate<ComputeMetadata> filter = com.google.common.base.Predicates.and(
                new GroupPredicate(name),
                new StatusPredicate());
        return driver.searchSingleNode(filter);
    }

    /**
     * TODO: Write a short summary of this type's roles and responsibilities.
     *
     * @author Niv Ingberg
     * @since 0.1
     */
    public abstract static class AbstractNodePredicate implements Predicate<ComputeMetadata> {
        @Override
        public boolean apply(ComputeMetadata input) {
            return input instanceof NodeMetadata && apply((NodeMetadata) input);
        }

        protected abstract boolean apply(NodeMetadata input);
    }

    /**
     * TODO: Write a short summary of this type's roles and responsibilities.
     *
     * @author Niv Ingberg
     * @since 0.1
     */
    public static class GroupPredicate extends AbstractNodePredicate {
        private final String expectedGroup;

        public GroupPredicate(String expectedGroup) {
            this.expectedGroup = expectedGroup;
        }

        @Override
        protected boolean apply(NodeMetadata input) {
            return expectedGroup.equals(input.getGroup());
        }
    }

    /**
     * TODO: Write a short summary of this type's roles and responsibilities.
     *
     * @author Niv Ingberg
     * @since 0.1
     */
    public static class StatusPredicate extends AbstractNodePredicate {
        @Override
        protected boolean apply(NodeMetadata input) {
            return input.getStatus() != NodeMetadata.Status.TERMINATED;
        }
    }
}
