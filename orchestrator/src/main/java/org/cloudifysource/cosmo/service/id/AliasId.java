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
 ******************************************************************************/
package org.cloudifysource.cosmo.service.id;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.google.common.base.Optional;
import com.google.common.base.Preconditions;
import org.cloudifysource.cosmo.service.lifecycle.LifecycleName;

import java.net.URI;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Represents an aliases such as "web/1".
 *
 * @see AliasGroupId
 *
 * @author itaif
 * @since 0.1
 */
public class AliasId {

    static final Pattern ALIAS_NAME_PATTERN = Pattern.compile("([a-zA-Z_/]+)/(\\d+)/?");

    private AliasGroupId aliasGroup;
    private int index;

    public AliasId(AliasGroupId aliasGroup, int index) {
        this.aliasGroup = aliasGroup;
        this.index = index;
    }

    public AliasId(String alias) {
        setAlias(alias);
    }

    @JsonIgnore
    public void setAlias(String alias) {

        final Matcher matcher = ALIAS_NAME_PATTERN.matcher(alias);
        final boolean found = matcher.find();
        Preconditions.checkArgument(found, "aliasGroup cannot be parsed by pattern " + ALIAS_NAME_PATTERN);
        Preconditions.checkArgument(
                matcher.groupCount() == 2,
                "aliasGroup cannot be parsed by pattern " + ALIAS_NAME_PATTERN);
        this.aliasGroup = new AliasGroupId(matcher.group(1));
        this.index = Integer.valueOf(matcher.group(2));
    }

    public String toString() {
        return aliasGroup.toString() + index + "/";
    }

    public AliasGroupId getAliasGroup() {
        return aliasGroup;
    }

    public void setAliasGroup(AliasGroupId aliasGroup) {
        this.aliasGroup = aliasGroup;
    }

    public int getIndex() {
        return index;
    }

    public void setIndex(int index) {
        this.index = index;
    }

    private static boolean isMatch(String alias) {
        final Matcher matcher = ALIAS_NAME_PATTERN.matcher(alias);
        return matcher.find() && matcher.groupCount() == 2;
    }

    public static Optional<AliasId> tryParse(String alias) {
        if (!isMatch(alias)) {
            return Optional.absent();
        }

        return Optional.fromNullable(new AliasId(alias));
    }

    /**
     * @param server - The URI of the http server.
     * @param lifecycle - The lifecycle that represents the instance id, in this alias.
     * @return - The URI of the machine.
     */
    public URI newInstanceId(URI server, LifecycleName lifecycle) {
        return URI.create(server + this.toString() + lifecycle.getFullName() + "/");
    }

    /**
     * @param server - The URI of the http server.
     * @return - The URI of the machine.
     */
    public URI newCloudMachineId(URI server) {
        return URI.create(server + this.toString() + "cloudmachine/");
    }
}
