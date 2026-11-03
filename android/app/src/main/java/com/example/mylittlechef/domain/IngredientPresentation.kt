// AI-assisted with Codex, 2026-11-02; human review pending.
package com.example.mylittlechef.domain

import com.example.mylittlechef.model.Ingredient
import java.text.Collator
import java.util.Locale

enum class IngredientCategory(val key: String, val label: String) {
    VEGETABLES("vegetables", "채소·버섯"), FRUIT("fruit", "과일"),
    MEAT("meat", "육류·육가공품"), SEAFOOD("seafood", "해산물·해조류"),
    EGGS_DAIRY("eggs_dairy", "달걀·유제품"), BEANS_NUTS("beans_nuts", "콩·두부·견과"),
    GRAINS("grains", "곡물·면·빵·떡"), PREPARED("prepared", "김치·절임·간편식"),
    SEASONINGS("seasonings", "양념·소스·기름"), LIQUIDS("liquids", "육수·음료"),
    OTHER("other", "기타·미분류");

    companion object {
        fun fromKey(key: String): IngredientCategory = requireNotNull(entries.find { it.key == key })
    }
}

data class IngredientAppearance(
    val categoryKey: String,
    val iconKey: String,
    val backgroundColor: String
) {
    val category: IngredientCategory get() = IngredientCategory.fromKey(categoryKey)
    val backgroundArgb: Long get() = 0xFF000000L or backgroundColor.drop(1).toLong(16)
}

enum class FridgeSortType(val label: String) {
    ADDED("추가순"), ALPHABETICAL("가나다순"), CATEGORY("분류순")
}

class IngredientPresentationCatalog private constructor(
    private val byName: Map<String, IngredientAppearance>,
    val ingredientIds: Map<String, Int>
) {
    val size: Int get() = byName.size

    // Aliases affect appearance only. Inventory names and deletion keys stay intact.
    fun appearanceFor(name: String): IngredientAppearance {
        val normalized = name.trim()
        return byName[normalized] ?: byName[DISPLAY_ALIASES[normalized]] ?: FALLBACK
    }

    companion object {
        private val FALLBACK = IngredientAppearance("other", "generic", "#E2E5E7")
        private val DISPLAY_ALIASES = mapOf("달걀" to "계란", "후춧가루" to "후추")
        val iconKeys: Set<String> = setOf(
            "leafy", "root", "fruit_vegetable", "onion", "scallion", "garlic", "sprouts",
            "mushroom", "fruit", "meat", "chicken", "fish", "shrimp", "squid", "seaweed",
            "egg", "milk", "cheese", "tofu", "beans", "rice", "noodles", "bread", "rice_cake",
            "kimchi", "seasoning", "stock", "generic"
        )
        private val HEADER = listOf("ingredient_id", "name", "category_key", "category",
            "icon_key", "background_color", "review_required", "review_note")

        fun fromCsv(csv: String): IngredientPresentationCatalog {
            val records = csvRecords(csv.removePrefix("\uFEFF"))
            require(records.firstOrNull() == HEADER) { "Unexpected ingredient presentation header" }
            val ids = mutableSetOf<Int>()
            val names = linkedMapOf<String, IngredientAppearance>()
            val ingredientIds = linkedMapOf<String, Int>()
            records.drop(1).forEach { row ->
                require(row.size == HEADER.size) { "Invalid ingredient presentation row" }
                val id = row[0].toIntOrNull()
                require(id != null && id > 0 && ids.add(id)) { "Invalid or duplicate ingredient ID" }
                val name = row[1]
                require(name.isNotBlank() && name == name.trim() && name !in names) {
                    "Invalid or duplicate ingredient name"
                }
                val category = IngredientCategory.fromKey(row[2])
                require(category.label == row[3]) { "Category key/label mismatch" }
                require(row[4] in iconKeys) { "Unknown ingredient icon" }
                require(Regex("#[0-9A-Fa-f]{6}").matches(row[5])) { "Invalid background color" }
                require(row[6] in setOf("true", "false")) { "Invalid review flag" }
                names[name] = IngredientAppearance(category.key, row[4], row[5])
                ingredientIds[name] = requireNotNull(id)
            }
            return IngredientPresentationCatalog(names, ingredientIds.toMap())
        }
    }
}

fun sortFridgeIngredients(
    ingredients: List<Ingredient>, type: FridgeSortType, catalog: IngredientPresentationCatalog
): List<Ingredient> {
    if (type == FridgeSortType.ADDED) return ingredients.toList()
    val collator = Collator.getInstance(Locale.KOREAN)
    return ingredients.sortedWith { a, b ->
        val categoryComparison = if (type == FridgeSortType.CATEGORY)
            catalog.appearanceFor(a.name).category.ordinal.compareTo(catalog.appearanceFor(b.name).category.ordinal)
        else 0
        if (categoryComparison != 0) categoryComparison else collator.compare(a.name, b.name)
    }
}

/** Read quoted commas, escaped quotes, CRLF and multiline notes from the CSV asset. */
private fun csvRecords(csv: String): List<List<String>> {
    val records = mutableListOf<List<String>>()
    val row = mutableListOf<String>()
    val field = StringBuilder()
    var quoted = false
    var index = 0
    fun finishRow() {
        row.add(field.toString())
        field.clear()
        if (row.size > 1 || row[0].isNotBlank()) records.add(row.toList())
        row.clear()
    }
    while (index < csv.length) {
        val char = csv[index]
        when {
            char == '"' && quoted && csv.getOrNull(index + 1) == '"' -> {
                field.append('"'); index++
            }
            char == '"' -> {
                require(quoted || field.isEmpty()) { "Invalid quote in CSV field" }
                quoted = !quoted
            }
            quoted -> field.append(char)
            char == ',' -> { row.add(field.toString()); field.clear() }
            char == '\r' || char == '\n' -> {
                finishRow()
                if (char == '\r' && csv.getOrNull(index + 1) == '\n') index++
            }
            else -> field.append(char)
        }
        index++
    }
    require(!quoted) { "Unclosed quoted CSV field" }
    if (field.isNotEmpty() || row.isNotEmpty()) finishRow()
    return records
}
