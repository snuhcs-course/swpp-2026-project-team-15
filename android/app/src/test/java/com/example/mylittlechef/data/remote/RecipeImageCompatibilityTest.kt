// Image compatibility checks assisted by Codex, 2026-11-03; human review pending.
package com.example.mylittlechef.data.remote

import com.example.mylittlechef.BuildConfig
import com.google.gson.Gson
import org.junit.Assert.*
import org.junit.Test

class RecipeImageCompatibilityTest {
    private val gson=Gson()
    private fun image(raw: String?): String? {
        val json="""{"id":7,"name":"두부김치","ingredients":[],"steps":[],"missing":[]} """
        val tree=gson.fromJson(json,com.google.gson.JsonObject::class.java)
        if(raw!=null) tree.addProperty("main_image_url",raw)
        val mapped=gson.fromJson(tree,RecipeDto::class.java).toRecipe()
        return gson.toJsonTree(mapped).asJsonObject.get("imageUrl")?.takeUnless { it.isJsonNull }?.asString
    }

    @Test fun relativeImageUsesConfiguredServerRoot() {
        assertEquals(BuildConfig.SERVER_BASE_URL.trimEnd('/')+"/recipe-images/7.jpg",image("/recipe-images/7.jpg"))
    }
    @Test fun absoluteImageIsRetained() {
        assertEquals("https://example.org/7.jpg",image("https://example.org/7.jpg"))
    }
    @Test fun oldResponseWithoutImageRemainsCompatible() { assertNull(image(null)); assertNull(image(" ")) }
    @Test fun unsupportedImageSchemeIsIgnored() { assertNull(image("file:///private/7.jpg")) }
}
