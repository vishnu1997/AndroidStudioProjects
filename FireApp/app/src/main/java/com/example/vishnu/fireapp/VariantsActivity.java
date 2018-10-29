package com.example.vishnu.fireapp;

import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.support.v7.app.AppCompatActivity;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.ImageView;
import android.widget.ListView;
import android.widget.TextView;
import android.widget.Toast;

import com.bumptech.glide.Glide;
import com.google.firebase.database.DataSnapshot;
import com.google.firebase.database.DatabaseError;
import com.google.firebase.database.DatabaseReference;
import com.google.firebase.database.FirebaseDatabase;
import com.google.firebase.database.ValueEventListener;

public class VariantsActivity extends AppCompatActivity {
    ImageView imageView;
    ListView listView;
    ListView listView2;
    String[] list;
    String[] list2;
    Context ins;
    String message;
    TextView textView;
    boolean checkSize,checkColor;
    String colorselected,sizeselected,nameSelected;
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        checkSize=false;
        checkColor=false;
        ins = this;

        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_variants);
        imageView = (ImageView)findViewById(R.id.imageView);
        Bundle bundle = getIntent().getExtras();
        message = bundle.getString("message");
        listView =(ListView)findViewById(R.id.listView);
        listView2 =(ListView)findViewById(R.id.listView2);
        textView=(TextView)findViewById(R.id.textView3);

        //setContentView(R.layout.activity_main);
        //// Write a message to the database
        FirebaseDatabase database = FirebaseDatabase.getInstance("https://connecteddressing.firebaseio.com/");
        DatabaseReference myRef = database.getReference(message);

        myRef.addValueEventListener(new ValueEventListener() {
            @Override
            public void onDataChange(DataSnapshot dataSnapshot) {
                for (DataSnapshot childDataSnapshot : dataSnapshot.getChildren()) {
                    String k = childDataSnapshot.getKey();
                    Log.v("Key",""+ childDataSnapshot.getKey()); //displays the key for the node
                    if(k.equals("image_url")){
                        Glide.with(getApplicationContext()).load(childDataSnapshot.getValue()).into(imageView);
                        continue;
                    }
                    if(k.equals("sizes")){
                        String va = (String)childDataSnapshot.getValue();
                        list = va.split(",");
                    }
                    if(k.equals("color")){
                        String va = (String)childDataSnapshot.getValue();
                        list2 = va.split(",");
                    }
                    if(k.equals("name")){
                        nameSelected = (String)childDataSnapshot.getValue();
                         textView.setText(nameSelected);
                    }
                    Log.v("ValueIn",""+ childDataSnapshot.getValue());   //gives the value for given keyname
                }






                ArrayAdapter<CharSequence> adapter =  new ArrayAdapter<CharSequence>(ins,android.R.layout.simple_list_item_1,list);
                listView.setAdapter(adapter);
                listView.setOnItemClickListener(new AdapterView.OnItemClickListener()
                {

                    @Override
                    public void onItemClick(AdapterView<?> parent, View view,
                                            int position, long id) {
                        sizeselected = list[position];
                        // TODO Auto-generated method stub
                        checkSize = true;
//                        for (int i = 0; i < listView.getChildCount(); i++) {
//                            if(position != i ){
//                                listView.getChildAt(i).setBackgroundColor(Color.TRANSPARENT);
//                            }
//                        }
                        //listView.getChildAt(position).setBackgroundColor(Color.parseColor("#ff0000"));
                        Toast.makeText(VariantsActivity.this, "Selected Size "+list[position], Toast.LENGTH_SHORT).show();
                    }
                });


                ArrayAdapter<CharSequence> adapters =  new ArrayAdapter<CharSequence>(ins,android.R.layout.simple_list_item_1,list2);
                listView2.setAdapter(adapters);



                listView2.setOnItemClickListener(new AdapterView.OnItemClickListener()
                {

                    @Override
                    public void onItemClick(AdapterView<?> parent, View view,
                                            int positions, long id) {
                        // TODO Auto-generated method stub

                        colorselected = list2[positions];
                        checkColor = true;
//                        for (int i = 0; i < listView2.getChildCount(); i++) {
//
//                            if(positions == i){
//                                if(list2[i].equals("Blue")) {
//                                    //Toast.makeText(VariantsActivity.this,"Inside Blue", Toast.LENGTH_SHORT).show();
//                                    listView2.getChildAt(i).setBackgroundColor(Color.parseColor("#0000ff"));
//
//                                }
//                                if(list2[i].equals("Yellow")) {
//                                    //Toast.makeText(VariantsActivity.this,"Inside Yellow", Toast.LENGTH_SHORT).show();
//                                    listView2.getChildAt(i).setBackgroundColor(Color.parseColor("#ffff00"));
//
//                                }
//                                if(list2[i].equals("Red")) {
//                                    //Toast.makeText(VariantsActivity.this,"Inside Red", Toast.LENGTH_SHORT).show();
//                                    listView2.getChildAt(i).setBackgroundColor(Color.parseColor("#ff0000"));
//
//                                }
//
//                            }else{
//
//                                listView2.getChildAt(i).setBackgroundColor(Color.TRANSPARENT);
//                            }
//                        }
                        Toast.makeText(VariantsActivity.this, "Selected Color "+list2[positions], Toast.LENGTH_SHORT).show();



                    }
                });







            }

            @Override
            public void onCancelled(DatabaseError databaseError) {

            }
        });





        /*ArrayAdapter<CharSequence> adapter =  new ArrayAdapter<CharSequence>(this,android.R.layout.simple_list_item_1,list);
        listView.setAdapter(adapter);
        listView.setOnItemClickListener(new AdapterView.OnItemClickListener()
        {

            @Override
            public void onItemClick(AdapterView<?> parent, View view,
                                    int position, long id) {
                sizeselected = list[position];
                // TODO Auto-generated method stub
                checkSize = true;
                for (int i = 0; i < listView.getChildCount(); i++) {
                    if(position == i ){
                        // listView.getChildAt(i).setBackgroundColor(Color.parseColor("#d0e836"));
                        if(list[position]=="6")
                            listView.getChildAt(i).setBackgroundColor(Color.parseColor("#d0e836"));
                        else
                            listView.getChildAt(i).setBackgroundColor(Color.parseColor("#ff0000"));

                    }else{
                        listView.getChildAt(i).setBackgroundColor(Color.TRANSPARENT);

                    }
                }
                Toast.makeText(VariantsActivity.this, list[position], Toast.LENGTH_SHORT).show();
            }
        });


        ArrayAdapter<CharSequence> adapters =  new ArrayAdapter<CharSequence>(this,android.R.layout.simple_list_item_1,list2);
        listView2.setAdapter(adapters);



        listView2.setOnItemClickListener(new AdapterView.OnItemClickListener()
        {

            @Override
            public void onItemClick(AdapterView<?> parent, View view,
                                    int positions, long id) {
                // TODO Auto-generated method stub

                colorselected = list2[positions];
                checkColor = true;
                for (int i = 0; i < listView2.getChildCount(); i++) {

                    if(positions == i){
                        if(list2[positions].equals("Blue")) {
                            //Toast.makeText(VariantsActivity.this,"Inside Blue", Toast.LENGTH_SHORT).show();
                            listView2.getChildAt(i).setBackgroundColor(Color.parseColor("#0000ff"));

                        }
                        if(list2[positions].equals("Yellow")) {
                            //Toast.makeText(VariantsActivity.this,"Inside Yellow", Toast.LENGTH_SHORT).show();
                            listView2.getChildAt(i).setBackgroundColor(Color.parseColor("#ffff00"));

                        }
                        if(list2[positions].equals("Red")) {
                            //Toast.makeText(VariantsActivity.this,"Inside Red", Toast.LENGTH_SHORT).show();
                            listView2.getChildAt(i).setBackgroundColor(Color.parseColor("#ff0000"));

                        }

                    }else{

                        listView2.getChildAt(i).setBackgroundColor(Color.TRANSPARENT);
                    }
                }


            }
        });*/

    }


    public void confirm(View view)
    {   for (int i=0;i<1;i++) {
        if (!checkSize) {
            Toast.makeText(VariantsActivity.this, "Please select Size", Toast.LENGTH_LONG).show();
            break;
        }
        if (!checkColor) {
            Toast.makeText(VariantsActivity.this, "Please select Color", Toast.LENGTH_SHORT).show();
            break;
        } else {
            Intent intent = new Intent(VariantsActivity.this, NextActivity.class);
            intent.putExtra("Name",nameSelected);
            intent.putExtra("Barcode",message);
            intent.putExtra("Size", sizeselected);
            intent.putExtra("Color", colorselected);
            startActivity(intent);
        }

    }

    }

}
