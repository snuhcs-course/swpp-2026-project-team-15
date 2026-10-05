package com.example.mylittlechef

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import com.example.mylittlechef.navigation.AppNavHost
import com.example.mylittlechef.ui.theme.MyLittleChefTheme

import com.example.mylittlechef.ui.onboarding.OnboardingNickname
import com.example.mylittlechef.ui.onboarding.OnboardingScreen

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            MyLittleChefTheme {
                AppNavHost()
                //Scaffold(modifier = Modifier.fillMaxSize())
                //{
                //    innerPadding ->
                //    OnboardingScreen(
                //        {},
                //        modifier = Modifier.padding(innerPadding)
                //    )
                //}
                //Scaffold(modifier = Modifier.fillMaxSize()) { innerPadding ->

                //Greeting(
                    //    name = "Android",
                    //    modifier = Modifier.padding(innerPadding)
                    //)
                //}
            }
        }
    }
}

@Composable
fun Greeting(name: String, modifier: Modifier = Modifier) {
    Text(
        text = "Hello $name!",
        modifier = modifier
    )
}

@Preview(showBackground = true)
@Composable
fun GreetingPreview() {
    MyLittleChefTheme {
        Greeting("Android")
    }
}