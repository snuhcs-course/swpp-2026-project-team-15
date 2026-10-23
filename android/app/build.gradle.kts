import java.net.URI

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
}

val serverBaseUrl = providers.gradleProperty("serverBaseUrl")
    .orElse("http://158.101.141.165/").get()
val serverEndpoint = URI(serverBaseUrl)
require(serverEndpoint.scheme in listOf("http", "https") && serverEndpoint.host != null &&
    serverEndpoint.userInfo == null && serverEndpoint.rawQuery == null &&
    serverEndpoint.rawFragment == null && serverBaseUrl.endsWith("/")) {
    "serverBaseUrl must be an HTTP(S) URL ending in /, without credentials, query or fragment"
}

android {
    namespace = "com.example.mylittlechef"
    compileSdk {
        version = release(37)
    }

    defaultConfig {
        applicationId = "com.example.mylittlechef"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"
        buildConfigField("String", "SERVER_BASE_URL", "\"$serverBaseUrl\"")

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    testBuildType = if (providers.gradleProperty("cloudDeviceTest").isPresent) "cloudTest" else "debug"

    buildTypes {
        debug {
            // JaCoCo report: ./gradlew createDebugUnitTestCoverageReport
            enableUnitTestCoverage = true
        }
        create("cloudTest") {
            initWith(getByName("debug"))
            applicationIdSuffix = ".cloudtest"
            versionNameSuffix = "-cloud-test"
            matchingFallbacks += listOf("debug")
            enableUnitTestCoverage = false
            resValue("string", "app_name", "MyLittleChef Cloud Test")
        }
        release {
            buildConfigField("String", "SERVER_BASE_URL", "\"${providers.gradleProperty("releaseServerBaseUrl").orElse("https://localhost/").get()}\"")
            optimization {
                enable = false
            }
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
    buildFeatures {
        compose = true
        buildConfig = true
        resValues = true
    }
}

dependencies {
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.navigation.compose)
    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.coroutines.test)
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.compose.ui.test.junit4)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(libs.androidx.junit)
    add("cloudTestImplementation", libs.androidx.compose.ui.test.manifest)
    add("cloudTestImplementation", libs.androidx.compose.ui.tooling)
    debugImplementation(libs.androidx.compose.ui.test.manifest)
    debugImplementation(libs.androidx.compose.ui.tooling)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.camera.core)
    implementation(libs.androidx.camera.camera2)
    implementation(libs.androidx.camera.lifecycle)
    implementation(libs.androidx.camera.view)
    implementation(libs.coil.compose)
    implementation(libs.retrofit)
    implementation(libs.retrofit.converter.gson)
    implementation(libs.androidx.datastore.preferences)
}
