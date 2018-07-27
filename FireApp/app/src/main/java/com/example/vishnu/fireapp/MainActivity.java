package com.example.vishnu.fireapp;

import android.content.Intent;
import android.os.Handler;
import android.support.v7.app.AppCompatActivity;
import android.os.Bundle;
import android.util.Log;
import android.view.WindowManager;
import android.widget.ImageView;

import com.bumptech.glide.Glide;
import com.google.firebase.database.DataSnapshot;
import com.google.firebase.database.DatabaseError;
import com.google.firebase.database.DatabaseReference;
import com.google.firebase.database.FirebaseDatabase;
import com.google.firebase.database.ValueEventListener;

import static android.provider.Contacts.SettingsColumns.KEY;

public class MainActivity extends AppCompatActivity {

    private static int SPLASH_TIME_OUT = 3000;
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        // Write a message to the database
//        FirebaseDatabase database = FirebaseDatabase.getInstance("https://connecteddressing.firebaseio.com/");
//        DatabaseReference myRef = database.getReference("U1234");
//
//        myRef.addValueEventListener(new ValueEventListener() {
//            @Override
//            public void onDataChange(DataSnapshot dataSnapshot) {
//                for (DataSnapshot childDataSnapshot : dataSnapshot.getChildren()) {
//                    String k = childDataSnapshot.getKey();
//                    Log.v("Key",""+ childDataSnapshot.getKey()); //displays the key for the node
//                    if(k.equals("image_url")){
//                        Glide.with(getApplicationContext()).load(childDataSnapshot.getValue()).into(imageView);
//                        continue;
//                    }
//                    Log.v("ValueIn",""+ childDataSnapshot.getValue());   //gives the value for given keyname
//                }
//            }
//
//            @Override
//            public void onCancelled(DatabaseError databaseError) {
//
//            }
//        });

        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN,
                WindowManager.LayoutParams.FLAG_FULLSCREEN);
        setContentView(R.layout.activity_main);
        new Handler().postDelayed(new Runnable() {
                                      @Override
                                      public void run() {
                                          Intent homeIntent = new Intent(MainActivity.this, HomeActivity.class);
                                          startActivity(homeIntent);
                                          finish();
                                      }
                                  }, SPLASH_TIME_OUT

        );

    }
}
