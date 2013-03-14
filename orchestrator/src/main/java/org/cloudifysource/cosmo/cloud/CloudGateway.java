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
import com.google.common.collect.Iterables;
import org.jclouds.ContextBuilder;
import org.jclouds.compute.ComputeServiceContext;
import org.jclouds.compute.RunNodesException;
import org.jclouds.compute.domain.ComputeMetadata;
import org.jclouds.compute.domain.NodeMetadata;
import org.jclouds.compute.domain.OsFamily;
import org.jclouds.compute.domain.Template;
import org.jclouds.ec2.domain.InstanceType;

import java.util.Set;

/**
 * TODO: Write a short summary of this type's roles and responsibilities.
 *
 * @author Niv Ingberg
 * @since 0.1
 */
public class CloudGateway {

    private final ComputeServiceContext context;
    private Template defaultTemplate;

    public static CloudGateway createEC2(String accessKeyId, String secretKey) {
        ContextBuilder builder = ContextBuilder.newBuilder("aws-ec2")
                .credentials(accessKeyId, secretKey);
        final ComputeServiceContext context = builder.build(ComputeServiceContext.class);
        return new CloudGateway(context);
    }

    public CloudGateway(ComputeServiceContext context) {
        this.context = context;
    }

    public void close() {
        context.close();
    }

    public NodeMetadata ensureStarted(String name) throws RunNodesException {
        final Optional<NodeMetadata> node = getByName(name);
        if (node.isPresent()) {
            final NodeMetadata.Status status = node.get().getStatus();
            switch (status) {
                case RUNNING:
                    return node.get();
                case SUSPENDED:
                    context.getComputeService().resumeNode(node.get().getId());
                    // TODO: GetByName again to refresh status.
                    return node.get();
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
        } else {
            return create(name);
        }
    }

    public void ensureDestoryed(String name) {
        final Optional<NodeMetadata> node = getByName(name);
        if (node.isPresent())
            destroy(node.get());
    }

    private Optional<NodeMetadata> getByName(String name) {
        Predicate<ComputeMetadata> filter = com.google.common.base.Predicates.and(
                new GroupPredicate(name),
                new StatusPredicate());
        final Set<? extends NodeMetadata> nodes = context.getComputeService().listNodesDetailsMatching(filter);
        if (nodes.isEmpty())
            return Optional.absent();
        return Optional.of(Iterables.getOnlyElement(nodes));
    }

    private NodeMetadata create(String name) throws RunNodesException {
        final Set<? extends NodeMetadata> nodes =
                context.getComputeService().createNodesInGroup(name, 1, getDefaultTemplate());
        return Iterables.getOnlyElement(nodes);
    }

    private void destroy(NodeMetadata node) {
        context.getComputeService().destroyNode(node.getId());
    }

    private Template getDefaultTemplate() {
        if (defaultTemplate == null) {
            defaultTemplate = context.getComputeService().templateBuilder()
                    .hardwareId(InstanceType.T1_MICRO)
                    .osFamily(OsFamily.AMZN_LINUX)
                    .build();
        }
        return defaultTemplate;
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
