package com.example.vishnu.vishnu;

import android.support.v7.app.AppCompatActivity;
import android.os.Bundle;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.widget.Button;
import android.widget.TextView;

public class avtivity extends AppCompatActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_avtivity);
        final Button button=(Button)findViewById(R.id.button);
        final TextView text=(TextView)findViewById(R.id.text2);
        final TextView text3=(TextView)findViewById(R.id.text3);
        final Button button2=(Button)findViewById(R.id.button2);
        final     Button button3=(Button)findViewById(R.id.button3);
        final Button button4=(Button)findViewById(R.id.button4);
        final Button button5=(Button)findViewById(R.id.button5);
        final Button button6=(Button)findViewById(R.id.button6);
        final Button button7=(Button)findViewById(R.id.button7);
        final Button button8=(Button)findViewById(R.id.button8);
        final Button button9=(Button)findViewById(R.id.button9);
        button.setText("click");
        button.setOnClickListener(new View.OnClickListener(){
            @Override
            public void onClick(View v){
                text.setText(button2.getText());
                text3.setText(button3.getText());

            }
        });

    }

    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        // Inflate the menu; this adds items to the action bar if it is present.
        getMenuInflater().inflate(R.menu.menu_avtivity, menu);
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        // Handle action bar item clicks here. The action bar will
        // automatically handle clicks on the Home/Up button, so long
        // as you specify a parent activity in AndroidManifest.xml.
        int id = item.getItemId();

        //noinspection SimplifiableIfStatement
        if (id == R.id.action_settings) {
            return true;
        }

        return super.onOptionsItemSelected(item);
    }
}
