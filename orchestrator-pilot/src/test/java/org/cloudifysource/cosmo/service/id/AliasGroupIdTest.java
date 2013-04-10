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

import org.testng.Assert;
import org.testng.annotations.Test;

/**
 * * Unit Tests for {@link AliasGroupId}.
 * @author itaif
 * @since 0.1
 */
public class AliasGroupIdTest {

    @Test
    public void testCorrectAliasGroupId() {
        Assert.assertEquals(AliasGroupId.tryParse("web").get().toString(), "web/");
        Assert.assertEquals(new AliasGroupId("web").toString(), "web/");
    }

    @Test
    public void testCorrectAliasGroupIdSlash() {
        Assert.assertEquals(AliasGroupId.tryParse("web/").get().toString(), "web/");
        Assert.assertEquals(new AliasGroupId("web/").toString(), "web/");
    }

    @Test
    public void testCorrectComplexAliasGroupId() {
        Assert.assertEquals(AliasGroupId.tryParse("myapp/web").get().toString(), "myapp/web/");
        Assert.assertEquals(new AliasGroupId("myapp/web").toString(), "myapp/web/");
    }

    @Test
    public void testCorrectComplexAliasGroupIdSlash() {
        Assert.assertEquals(AliasGroupId.tryParse("myapp/web/").get().toString(), "myapp/web/");
        Assert.assertEquals(new AliasGroupId("myapp/web/").toString(), "myapp/web/");
    }

    @Test(expectedExceptions = {IllegalArgumentException.class })
    public void testIncorrectAliasGroupId() {
        Assert.assertFalse(AliasGroupId.tryParse("web/1").isPresent());
        new AliasGroupId("web/1");
    }

    @Test(expectedExceptions = {IllegalArgumentException.class })
    public void testIncorrectAliasGroupIdSlash() {
        Assert.assertFalse(AliasGroupId.tryParse("web/1/").isPresent());
        new AliasGroupId("web/1/");
    }
}
