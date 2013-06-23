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

package org.cloudifysource.cosmo.dsl;

import org.testng.annotations.Test;

import static org.fest.assertions.api.Assertions.assertThat;

/**
 * @author Idan Moyal
 * @since 0.1
 */
public class ResourceLocationHelperTest {

    @Test
    public void testGetParentLocation() {
        String location = "org/cloudifysource/cosmo/test";
        String parentLocation = ResourceLocationHelper.getParentLocation(location);
        assertThat(parentLocation).isEqualTo("org/cloudifysource/cosmo");
        location = location + "/";
        parentLocation = ResourceLocationHelper.getParentLocation(location);
        assertThat(parentLocation).isEqualTo("org/cloudifysource/cosmo");
        location = "test";
        parentLocation = ResourceLocationHelper.getParentLocation(location);
        assertThat(parentLocation).isEqualTo("");
    }

    @Test
    public void testCreateLocationString() {
        String expected = "org/cloudifysource/cosmo/test/sub";
        String base = "org/cloudifysource/cosmo/test";
        String location = ResourceLocationHelper.createLocationString(base, "sub");
        assertThat(location).isEqualTo(expected);
        base = "org/cloudifysource/cosmo/test";
        location = ResourceLocationHelper.createLocationString(base, "/sub");
        assertThat(location).isEqualTo(expected);
        base = "org/cloudifysource/cosmo/test/";
        location = ResourceLocationHelper.createLocationString(base, "sub");
        assertThat(location).isEqualTo(expected);
        base = "org/cloudifysource/cosmo/test/";
        location = ResourceLocationHelper.createLocationString(base, "/sub");
        assertThat(location).isEqualTo(expected);
        base = "";
        location = ResourceLocationHelper.createLocationString(base, "/sub");
        assertThat(location).isEqualTo("/sub");
        base = "/";
        location = ResourceLocationHelper.createLocationString(base, "/sub");
        assertThat(location).isEqualTo("/sub");
    }

}
