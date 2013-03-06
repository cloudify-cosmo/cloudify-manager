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
 * Unit Tests for {@link AliasId}.
 * @author itaif
 * @since 0.1
 */
public class AliasIdTest {

    @Test
    public void testCorrectAliasId() {
        Assert.assertEquals(AliasId.tryParse("web/1").get().toString(), "web/1/");
        Assert.assertEquals(new AliasId("web/1").toString(), "web/1/");
    }

    @Test
    public void testCorrectAliasIdSlash() {
        Assert.assertEquals(AliasId.tryParse("web/1/").get().toString(), "web/1/");
        Assert.assertEquals(new AliasId("web/1/").toString(), "web/1/");
    }

    @Test(expectedExceptions = {IllegalArgumentException.class })
    public void testIncorrectAliasId() {
        Assert.assertFalse(AliasId.tryParse("web").isPresent());
        new AliasId("web");
    }

    @Test(expectedExceptions = {IllegalArgumentException.class })
    public void testIncorrectAliasIdSlash() {
        Assert.assertFalse(AliasId.tryParse("web/").isPresent());
        new AliasId("web/");
    }

    @Test(expectedExceptions = {IllegalArgumentException.class })
    public void testIncorrectAliasIdNonNumber() {
        Assert.assertFalse(AliasId.tryParse("web/x").isPresent());
        new AliasId("web/x");
    }
}
