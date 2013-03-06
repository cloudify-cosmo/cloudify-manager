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

import com.google.common.base.Optional;
import com.google.common.base.Preconditions;
import org.cloudifysource.cosmo.service.lifecycle.LifecycleName;

import java.net.URI;
import java.util.regex.Pattern;

/**
 * Represents a group of aliases.
 * For example "web" represents the aliases "web/1","web/2","web/3",etc...
 *
 * @see AliasId
 * @author itaif
 * @since 0.1
 */
public class AliasGroupId {

    static final Pattern ALIAS_GROUP_NAME_PATTERN = Pattern.compile("[a-zA-Z_/]+");

    String aliasGroup;

    public AliasGroupId() {
    }

    public AliasGroupId(String aliasGroup) {
        setAliasGroup(aliasGroup);
    }

    public String getAliasGroup() {
        return aliasGroup;
    }

    public void setAliasGroup(String aliasGroup) {
        final boolean matches = isMatch(aliasGroup);
        Preconditions.checkArgument(matches, "aliasGroup cannot be parsed by pattern " + ALIAS_GROUP_NAME_PATTERN);
        if (aliasGroup.endsWith("/")) {
            this.aliasGroup = aliasGroup;
        } else {
            this.aliasGroup = aliasGroup + "/";
        }

    }

    private static boolean isMatch(String aliasGroup) {
        return ALIAS_GROUP_NAME_PATTERN.matcher(aliasGroup).matches();
    }

    public AliasId newAliasId(int index) {
        return new AliasId(this, index);
    }

    public String toString() {
        return aliasGroup;
    }

    public static Optional<AliasGroupId> tryParse(String aliasGroup) {
        if (!isMatch(aliasGroup)) {
            return Optional.absent();
        }

        return Optional.fromNullable(new AliasGroupId(aliasGroup));
    }

    public URI newServiceId(URI server, LifecycleName lifecycle) {
        return URI.create(server + aliasGroup + lifecycle.getName() + "/");
    }
}
