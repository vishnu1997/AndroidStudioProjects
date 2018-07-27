package com.example.vishnu.fireapp;

import android.content.Intent;
import android.support.v7.app.AppCompatActivity;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

import com.google.firebase.database.DatabaseReference;
import com.google.firebase.database.FirebaseDatabase;

public class NextActivity extends AppCompatActivity {
    TextView t1,t2,t3;
    Boolean flag ;
    private Button button;
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_next);
        button = (Button) findViewById(R.id.button2);
        Intent intent = getIntent();
        flag = true;
        final String name = intent.getStringExtra("Name");

        final String size = intent.getStringExtra("Size");
         final String color = intent.getStringExtra("Color");
        final String barcode = intent.getStringExtra("Barcode");
        t3 =(TextView)findViewById(R.id.textView7);

        t1 =(TextView)findViewById(R.id.textView4);
        t2 =(TextView)findViewById(R.id.textView5);
        t1.setText(size);
        t2.setText(color);
        t3.setText(name);

        FirebaseDatabase database = FirebaseDatabase.getInstance("https://requested-c673b.firebaseio.com/");
        final DatabaseReference myRef = database.getReference("Vishnu");

        button.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                if(flag){
                    Toast.makeText(NextActivity.this,"Requested, Please Wait." , Toast.LENGTH_SHORT).show();
                    flag = false;
                    myRef.setValue("Requested "+name +"("+barcode+")"+" of Size "+size+" and of color "+color);
                }else{
                    Toast.makeText(NextActivity.this,"Already Requested" , Toast.LENGTH_SHORT).show();

                }

            }
        });


    }
}
